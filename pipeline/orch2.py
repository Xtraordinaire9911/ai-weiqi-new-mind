# 无人值守流水线: 视频(下载->转写->识谱) -> 按SGF分组合并树 -> KataGo局部分析 -> 合成带解析SGF
import json,os,sys,subprocess,glob,re,threading,time,traceback
from concurrent.futures import ThreadPoolExecutor
from treesync import tree_fingerprint,check_analysis,check_kp,kp_ident,USABLE
import sgfcheck,fixtext
from collections import Counter
from wqutil import atomic_write_json,atomic_write_text,read_json,find_ffmpeg,setup_stdio,utf8_env,Log,Manifest,retry_with_backoff,single_instance   # atomic outputs: a kill mid-write must not leave partial files
# Dirs come from env vars when set (tests, another machine); the defaults are the original Windows paths.
HERE=os.path.dirname(os.path.abspath(__file__))   # sibling scripts (tr.py, board.py, analyze2.py) are looked up here, not in a hard coded dir
W=os.environ.get('WEIQI_WORK',r'D:\tmp\work');V=os.environ.get('WEIQI_VID',r'D:\tmp\vid')
PROJ=os.environ.get('WEIQI_PROJ',r'D:\workspace\fun\Weiqi\Weiqi_AI\josekiapp')
SOURCE=os.environ.get('WEIQI_SOURCE','chenlintao');SEASON=int(os.environ.get('WEIQI_SEASON','1500387'))   # uploader folder under data/sources + playlist (season) id
MAXIDX=int(os.environ.get('WEIQI_MAX_IDX','49'))   # groups that contain a later video are skipped (not downloaded yet)
def _find_py():   # interpreter for the child scripts: env, the Python 3.12 this pipeline was built with, else the current one
    if os.environ.get('WEIQI_PY'):return os.environ['WEIQI_PY']
    c=os.path.join(os.environ.get('LOCALAPPDATA',''),'Programs','Python','Python312','python.exe')
    return c if os.path.exists(c) else sys.executable
PY=_find_py()
FF=find_ffmpeg()   # None when missing: stageA reports a clear error instead of an IndexError at import time
def load_sources():
    """(Re)load index.json and plan.json of SOURCE. Returns an error text instead of raising, so importing this module never fails."""
    global IDX,PLAN,vid
    d=os.path.join(PROJ,'data','sources',SOURCE)
    try:IDX=read_json(os.path.join(d,'index.json'));PLAN=read_json(os.path.join(d,'plan.json'))
    except (OSError,ValueError) as e:IDX,PLAN,vid=[],{'merge':{},'series':{}},{};return str(e)
    vid={x['idx']:x for x in IDX if x['season']==SEASON};return ''
SRC_ERR=load_sources()
DL=threading.Semaphore(1)
log=Log(lambda:os.path.join(W,'logs','orch2.log'))   # console + utf-8 file W/logs/orch2.log (survives a cp936 console and restarts)
ENV=utf8_env()   # utf-8 text mode for every child process
def D(i):return os.path.join(W,'v',str(i))   # per video cache dir: v.mp4, t.json (transcript), b.json (board frames)
# ---- 阶段A: 单视频 ----
SLEEP=time.sleep   # indirection so tests can skip the waiting
DL_TRIES=int(os.environ.get('WEIQI_DL_TRIES','4'));DL_BACKOFF=float(os.environ.get('WEIQI_DL_BACKOFF','60'))   # waits 60, 180, 540 s between tries
DL_TIMEOUT=float(os.environ.get('WEIQI_DL_TIMEOUT','1800'));STAGE_TIMEOUT=float(os.environ.get('WEIQI_STAGE_TIMEOUT','7200'))   # a hung child must not hold a pool slot for ever
RETRY_ROUNDS=int(os.environ.get('WEIQI_RETRY_ROUNDS','1'));RETRY_WAIT=float(os.environ.get('WEIQI_RETRY_WAIT','600'))   # second chance for failed videos at the end of a run
FAILED=Manifest(lambda:os.path.join(W,'failed_videos.json'))   # which videos failed, in which stage, and why
class StageError(RuntimeError):
    def __init__(self,stage,msg):super().__init__(msg);self.stage=stage
def tail(b,n=300):   # last bit of a child's stderr as text
    return b.decode('utf-8','replace').strip()[-n:] if b else ''
def failure_reason(err):
    """One line that says why yt-dlp produced no file."""
    m=re.search(r'HTTP Error (\d+)',err)
    if m:return 'HTTP %s%s'%(m.group(1),' (throttled)' if m.group(1) in ('412','429','567') else '')
    lines=[x.strip() for x in err.splitlines() if x.strip()]
    return lines[-1][:200] if lines else 'yt-dlp produced no file and no error text'
def probe_duration(path):
    """Length in seconds from `ffmpeg -i`, None if unreadable. Catches truncated downloads and preview clips."""
    if not FF:return None
    try:r=subprocess.run([FF,'-hide_banner','-i',path],capture_output=True,env=ENV,timeout=60)
    except (OSError,subprocess.TimeoutExpired):return None
    m=re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)',r.stderr.decode('utf-8','replace'))
    return int(m.group(1))*3600+int(m.group(2))*60+float(m.group(3)) if m else None
def download(i):
    """Fetch v.mp4 with backoff between tries. The download slot DL is held only while yt-dlp runs, never while waiting between tries,
    so one throttled video (HTTP 567) cannot block the others, and after DL_TRIES it gives up instead of holding a pool slot for ever."""
    b=vid[i]['bvid'];mp4=os.path.join(D(i),'v.mp4');want=vid[i].get('sec')
    def attempt():
        with DL:
            try:r=subprocess.run([PY,'-m','yt_dlp','-f','bv*[height<=720][vcodec^=avc]+ba/b[height<=720]/b','--merge-output-format','mp4','--ffmpeg-location',os.path.dirname(FF),'--retries','10','-N','1','--sleep-requests','1','-o',mp4,'https://www.bilibili.com/video/'+b],capture_output=True,env=ENV,timeout=DL_TIMEOUT)
            except subprocess.TimeoutExpired:return False,'yt-dlp timed out after %ds'%DL_TIMEOUT
        if os.path.exists(mp4) and os.path.getsize(mp4)>1e6:
            got=probe_duration(mp4)
            if got and want and got<0.8*want:   # truncated, or a different (preview) video
                os.replace(mp4,mp4+'.short');return False,'file too short: %ds, expected %ds'%(got,want)
            return True,''
        return False,failure_reason(r.stderr.decode('utf-8','replace'))
    ok,why=retry_with_backoff(attempt,tries=DL_TRIES,base=DL_BACKOFF,sleep=lambda s:SLEEP(s),log=lambda *a:log('A',i,*a))
    if not ok:raise StageError('download',why)
def child(stage,args):
    """Run a stage script. A failure carries the stage name and the end of its stderr (it used to be captured and dropped)."""
    try:r=subprocess.run(args,capture_output=True,env=ENV,timeout=STAGE_TIMEOUT)
    except subprocess.TimeoutExpired:raise StageError(stage,'timed out after %ds'%STAGE_TIMEOUT)
    if r.returncode:raise StageError(stage,'exit code %d: %s'%(r.returncode,tail(r.stderr)))
def rejected(p):
    """Reason when a stage already rejected this video (<name>.rej.json), so the heavy work is not repeated for the same verdict.
    WEIQI_RETRY_REJECTED=1 forgets old verdicts (after fixing the recogniser, say)."""
    rj=os.path.splitext(p)[0]+'.rej.json'
    if not os.path.exists(rj):return ''
    if os.environ.get('WEIQI_RETRY_REJECTED'):os.remove(rj);return ''
    return '; '.join(read_json(rj,default={}).get('reasons',['rejected']))
def stageA(i):
    if not FF:raise StageError('setup','ffmpeg not found (set FFMPEG=path)')
    os.makedirs(D(i),exist_ok=True);mp4=os.path.join(D(i),'v.mp4');tj=os.path.join(D(i),'t.json');bj=os.path.join(D(i),'b.json')
    for p in (tj,bj):   # a json left half written by a killed run is moved aside, so its stage runs again
        if os.path.exists(p):read_json(p,default=None,quarantine=True)
    if not os.path.exists(mp4) and not (os.path.exists(tj) and os.path.exists(bj)):download(i)   # no download when only the video is gone
    # board first: its layout check is cheap and a video that fails it (other layout) saves the long whisper run
    for p,stage,cmd in ((bj,'board',[PY,os.path.join(HERE,'board.py'),mp4,bj,FF]),(tj,'transcribe',[PY,os.path.join(HERE,'tr.py'),mp4,tj])):
        if os.path.exists(p):continue
        why=rejected(p)
        if why:raise StageError(stage,'rejected earlier: '+why)
        child(stage,cmd)
    log('A done',i,vid[i]['title'])
def process_video(i):
    """stageA that never raises. True when the video is ready; otherwise False, with the reason in the log and in failed_videos.json."""
    try:stageA(i);FAILED.clear(i);return True
    except Exception as e:
        stage=getattr(e,'stage','error');why=str(e) or e.__class__.__name__;v=vid.get(i,{})
        log('A FAIL',i,v.get('title',''),'|',stage,'|',why)
        try:FAILED.record(i,bvid=v.get('bvid'),title=v.get('title'),stage=stage,reason=why[:400])
        except OSError:pass
        return False
# ---- 分组树 (多视频合并) ----
C=18;DT=1/6
def build_tree(vids):
    st=lambda s:frozenset((i,ch) for i,ch in enumerate(s) if ch!='.')
    nodes=[{'pos':frozenset(),'par':None,'mv':None,'v':[],'ch':[],'setup':False}];index={frozenset():0}
    def new(pos,par,mv,t,vi,setup=False):
        nodes.append({'pos':pos,'par':par,'mv':mv,'v':[[t,t+DT,vi]],'ch':[],'setup':setup});nodes[par]['ch'].append(len(nodes)-1);return len(nodes)-1
    for vi,i in enumerate(vids):
        fr=read_json(os.path.join(D(i),'b.json'));cur=None;prevs=None
        for t,s in fr:
            if s is None:continue
            if s==prevs:
                if cur is not None:nodes[cur]['v'][-1][1]=t+DT
                continue
            prevs=s;P=st(s)
            def visit(c):
                v=nodes[c]['v']
                if v and v[-1][2]==vi and t-v[-1][1]<0.5:v[-1][1]=t+DT
                else:v.append([t,t+DT,vi])
            if cur is None:
                if P in index:cur=index[P];visit(cur)
                else:cur=new(P,0,None,t,vi,True);index[P]=cur
                continue
            if P in index:cur=index[P];visit(cur);continue
            order=sorted(range(len(nodes)),key=lambda k:(len(nodes[k]['pos']^P),k!=cur));b=order[0];N=nodes[b]['pos'];add=P-N;rem=N-P
            if len(add)==1 and all(c!=list(add)[0][1] for _,c in rem):cur=new(P,b,list(add)[0],t,vi);index[P]=cur
            else:cur=new(P,0,None,t,vi,True);index[P]=cur
    dw=lambda n:sum(b-a for a,b,_ in n['v'])
    ch=True
    while ch:
        ch=False
        for k,n in enumerate(nodes):
            if k==0 or n.get('dead'):continue
            if any(not nodes[c].get('dead') for c in n['ch']):continue
            if dw(n)<0.5 or (n['setup'] and True):
                n['dead']=True;nodes[n['par']]['ch'].remove(k);ch=True
    out=[]
    for k,n in enumerate(nodes):
        d={'id':k,'par':n['par'],'mv':n['mv'],'v':n['v'],'ch':n['ch'],'dead':n.get('dead',False),'setup':n['setup'],'n':len(n['pos'])}
        d['pos']=''.join(sorted('%s%d'%(c,q) for q,c in n['pos']));out.append(d)
    return out
# ---- 分组合成 SGF ----
L='ABCDEFGHJKLMNOPQRST';gtp=lambda k:L[k%C]+str(19-k//C);sg=lambda k:chr(97+k%C)+chr(97+k//C)
sg_=lambda m:chr(97+L.index(m[0]))+chr(97+19-int(m[1:]))
CN={'B':'黑','W':'白'}
FIRED=Counter()   # which typo rules fired while merging the current group (written to fixlog_<group>.json)
def fix(t):   # typo dictionary: built in rules + W/fixdict.json, longest first, repeated until stable (see fixtext.py), idempotent
    return fixtext.fixer_for(os.path.join(W,'fixdict.json')).apply(t,FIRED)
def mm(vi,t):return '@%d|%d:%02d'%(vi,t//60,t%60)
def esc(s):return s.replace('\\','\\\\').replace(']','\\]')
def clean_cands(cs):   # keep candidates whose move is a board coordinate; 'pass' or garbage would put an invalid entry into AN[]
    return [dict(m,pv=[x for x in m['pv'] if sgfcheck.GTP.fullmatch(x)]) for m in cs if sgfcheck.GTP.fullmatch(m['m'])]
DUMP=[]
def merge(N,A,vids,name,summ='',KP={}):
    DUMP.clear();FIRED.clear()   # a failed merge of an earlier group must not leak its nodes into this group's kpin dump
    T=[read_json(os.path.join(D(i),'t.json')) for i in vids]
    IV=sorted((a,b,k,vi) for k,n in enumerate(N) if not n['dead'] for a,b,vi in n['v'])
    SEG={}
    for vi,tt in enumerate(T):
        ivs=[x for x in IV if x[3]==vi]
        for q,s in enumerate(tt):
            t=s['s']+.3;best=None
            for a,b,k,_ in ivs:
                if a<=t:best=k
                else:break
            SEG.setdefault(best,[]).append((vi,q))
    live=lambda k:sorted([c for c in N[k]['ch'] if not N[c]['dead']],key=lambda c:min(a for a,_,v in N[c]['v']))
    def teacher(k):
        sg_l=SEG.get(k,[]);
        if not sg_l:return '',None
        txt=[];first=None
        for vi,q in sg_l:
            if first is None:first=(vi,T[vi][q]['s'])
            txt.append(T[vi][q]['t'].strip())
        return fix(''.join(txt)),first
    def ai(k):
        a=A.get('%d'%k)
        if not a or 'cand' not in a:return '',''
        c0=clean_cands(a['cand'])
        if not c0:return '',''
        srch=[m for m in c0 if not m.get('f')];tv=max([m['v'] for m in srch] or [1])
        c=[m for m in c0 if m.get('f') or m['v']>=max(5,.08*tv)] or c0[:1]
        best=max(c,key=lambda m:m['s']);c=sorted(c,key=lambda m:-m['s']);ls=[]
        def cs(m):return "⟨%s⟩%s"%(m['m'],"最优" if m is best else "%+.1f目"%(m['s']-best['s']))+("(老师走的)" if m.get('f') else "")
        ls.append("【AI局部评估】%s先。只在本定式涉及的区域内搜索,不看全盘胜率;数字=比局部最优差几目(0最优,越负越差)。局部最优⟨%s⟩;候选: "%(CN[a['turn']],best['m'])+' '.join(cs(m)+("/先验%d%%"%round(m['p']*100) if m['p']>=0 else "") for m in c[:6]))
        ls.append('最优变化 ⟨'+' '.join(best['pv'])+'⟩')
        for ch in live(k):
            if N[ch]['mv'] is None:continue
            m=gtp(N[ch]['mv'][0]);cm=next((x for x in c if x['m']==m),None)
            ls.append('视频变化⟨%s⟩:'%m+(("就是AI局部最优" if cm is best else "比局部最优差%.1f目"%(best['s']-cm['s'])) if cm else "区域外着法(脱先/他处),未评估"))
        b=A.get('%d_0'%k)
        if b and 'cand' in b and b['cand']:
            bc=[m for m in b['cand'] if m['v']>=max(5,.08*max(x['v'] for x in b['cand']))] or b['cand'][:1];nb=max(bc,key=lambda m:m['s'])
            ls.append("【周边子力影响】去掉区域外的子力后,局部最优为⟨%s⟩;带着外围子力时为⟨%s⟩"%(nb['m'],best['m'])+(" → 结论一致,外围影响小" if nb['m']==best['m'] else " → 外围子力改变了选择,需结合周边配置判断"))
        return chr(10).join(ls),';'.join("%s:%.1f:%.2f:%d:%d:%s"%(sg_(m['m']),m['s']-best['s'],m['p'],round(m['wr']*100),m['v'],' '.join(m['pv'])) for m in c[:10])
    def node(k):
        n=N[k];s=''
        if n['mv']:s+=';%s[%s]'%(n['mv'][1],sg(n['mv'][0]))
        elif k:
            st={'B':[],'W':[]}
            for t_ in re.findall(r'[BW]\d+',n['pos']):st[t_[0]].append(sg(int(t_[1:])))
            s+=';'+''.join('A%s'%c+''.join('[%s]'%p for p in v) for c,v in st.items() if v)
        t,f=teacher(k);aitxt,an=ai(k);txt=''
        aa=A.get('%d'%k)
        if aa and 'turn' in aa:s+='PL[%s]'%aa['turn']
        if not n['mv'] and k and n['par']==0:
            stt=re.findall(r'([BW])(\d+)',n['pos']);txt+='【起手局面】'+' '.join(('黑' if c=='B' else '白')+gtp(int(q)) for c,q in stt)+chr(10)
        if t and len(t)>=60:
            pth=[];q=k
            while q:
                if N[q]['mv']:pth.append(N[q]['mv'][1]+gtp(N[q]['mv'][0]))
                q=N[q]['par']
            DUMP.append({'id':k,'path':' '.join(reversed(pth)),'text':t,'nch':len(live(k))})
        if k==0 and summ:txt+=summ+'\n'
        if t:txt+='【老师讲解 %s】%s\n'%(mm(*f),t)
        elif n['mv'] and n['v']:txt+=mm(n['v'][0][2],n['v'][0][0])+'\n'
        if KP.get(str(k)):txt+='【要点与考量】'+fix(KP[str(k)])+chr(10)
        txt+=aitxt
        if txt.strip():s+='C[%s]'%esc(txt.strip())
        if an:s+='AN[%s]'%an
        ch=live(k)
        if len(ch)==1:return s+node(ch[0])
        return s+''.join('('+node(c)+')' for c in ch)
    return '(;GM[1]FF[4]CA[UTF-8]SZ[19]KM[6.5]GN[%s]PC[%s]%s)'%(esc(name),esc((PLAN.get('name') or SOURCE)+' '+' '.join(vid[i]['bvid'] for i in vids)),node(0))   # GN/PC are escaped like every other text value
# ---- 阶段B: 分组 ----
def sgf_path(name):   # data/sgf/<uploader>/<series>/<group>.sgf; the series folder name comes from plan.json
    return os.path.join(PROJ,'data','sgf',SOURCE,PLAN['series'][str(SEASON)],name+'.sgf')
def validate_plan():
    """Problems in index.json / plan.json that would otherwise show up much later as a KeyError or a stray file. Every new uploader brings its own pair of files."""
    ser=str(SEASON);bad=[]
    merge_=PLAN.get('merge',{}).get(ser)
    if merge_ is None:return ['plan.json has no merge list for season %s'%ser]
    if ser not in PLAN.get('series',{}):bad.append('plan.json has no series name for season %s'%ser)
    names={}
    for name,idxs in merge_:
        if safe_name(name)!=name or not name.strip():bad.append('group name %r is not a usable file name (these characters are not allowed: \\ / : * ? " < > |)'%name)
        if name in names:bad.append('group name %r appears twice'%name)
        names[name]=1
        for i in idxs:
            if i not in vid:bad.append('group %r: video %s is not in index.json for season %s'%(name,i,ser))
    return bad
def groups():
    if SRC_ERR:raise RuntimeError('cannot read index.json/plan.json: '+SRC_ERR)
    bad=validate_plan()
    if bad:raise RuntimeError('plan.json does not fit index.json:\n  '+'\n  '.join(bad))
    out=[]
    for name,idxs in PLAN['merge'][str(SEASON)]:
        if any(x>MAXIDX for x in idxs):continue
        out.append((name,idxs))
    return out
def sgf_decision(path,sgf,force=False):
    """May sgf replace the file at path? Not when it is invalid or poorer than the file already there (fewer nodes, less AI data or notes). Returns (ok, reasons)."""
    bad=sgfcheck.validate(sgf)
    if bad:return False,['new sgf is invalid: '+'; '.join(bad[:3])]
    if not os.path.isdir(os.path.dirname(path)):return False,['target folder does not exist: '+os.path.dirname(path)]   # a wrong path must not create stray files
    if os.path.exists(path) and not force:
        with open(path,encoding='utf-8-sig') as f:old=f.read()
        if not sgfcheck.validate(old):   # a damaged old file may be replaced, a good one only by an equal or richer one
            why=sgfcheck.worse(sgfcheck.metrics(sgf),sgfcheck.metrics(old))
            if why:return False,['would lose data: '+', '.join(why)]
    return True,[]
def write_sgf(path,sgf,force=False):
    """sgf_decision, then an atomic write when it says yes. Returns (written, reasons)."""
    ok,why=sgf_decision(path,sgf,force)
    if ok:atomic_write_text(path,sgf)
    return ok,why
ANALYZE_TIMEOUT=float(os.environ.get('WEIQI_ANALYZE_TIMEOUT','21600'))   # seconds; a hung analysis must not block the pipeline for ever
def run_analysis(base,a2,safe):
    """Run analyze2.py for one group. Its output goes to W/logs/analyze_<group>.log (it used to be captured and thrown away, so progress was invisible)
    and a failure is reported. Progress with ETA is also in <a2>.progress.log; an interrupted run resumes from <a2>.part next time."""
    lp=os.path.join(W,'logs','analyze_%s.log'%safe);os.makedirs(os.path.dirname(lp),exist_ok=True)
    try:
        with open(lp,'ab') as lf:
            r=subprocess.run([PY,os.path.join(HERE,'analyze2.py'),base+'.n.json',a2,'220','100'],stdout=lf,stderr=subprocess.STDOUT,env=ENV,timeout=ANALYZE_TIMEOUT)
        if r.returncode:log('B WARN analyze2 exit code',r.returncode,'- see',lp)
    except subprocess.TimeoutExpired:log('B WARN analyze2 timed out after',ANALYZE_TIMEOUT,'s, the checkpoint is kept and the next run continues')
    except OSError as e:log('B WARN cannot run analyze2:',e)
def safe_name(name):return re.sub(r'[\\/:*?"<>|]','',name)   # group name -> file name part
def stageB(name,idxs,visits=150,force=False,planned=None,dry=False):
    """Build one group. dry=True does everything in memory and writes nothing (not even caches): it only says what would happen to the SGF."""
    safe=safe_name(name);base=os.path.join(W,'g_'+safe)
    put=lambda f,*a,**k:None if dry else f(*a,**k)   # every write goes through this
    rep={'group':name,'videos':list(idxs),'time':time.strftime('%Y-%m-%d %H:%M:%S')}   # one status record per group: status_<group>.json
    if planned and set(planned)-set(idxs):   # some videos of the group failed: the SGF is built from the rest and rebuilt when they arrive
        rep['missing_videos']=sorted(set(planned)-set(idxs));log('B WARN',name,'is partial, missing videos',rep['missing_videos'])
    N=build_tree(idxs);fp=tree_fingerprint(N);put(atomic_write_json,base+'.n.json',N)
    rep.update(tree_fp=fp,nodes=sum(1 for n in N if not n['dead']))
    # --- analysis: it must belong to exactly this tree, otherwise redo it (or leave the AI part out); never merge a mismatch
    a2=base+'.a2.json'
    A=read_json(a2,default=None);st,msg=check_analysis(N,A)   # explicit utf-8; a damaged file reads as missing
    if st not in USABLE and not os.environ.get('NOAN') and not dry:
        if st!='missing':log('B',name,'analysis is',st,'-',msg,'-> running it again');os.replace(a2,a2+'.stale')   # keep the old file for inspection, it is never merged
        run_analysis(base,a2,safe)
        A=read_json(a2,default=None);st,msg=check_analysis(N,A)
    if st not in USABLE:
        if st!='missing':log('B WARN',name,'analysis not used:',st,msg)
        A={}
    elif st=='legacy':log('B WARN',name,msg)
    rep['analysis']={'status':st,'message':msg}
    # --- key point notes (kp): same rule. A kp file without _meta that is newer than the last kpin dump was written from that dump.
    sp=os.path.join(W,'summary_%s.md'%safe);summ=open(sp,encoding='utf-8').read() if os.path.exists(sp) else ''
    kp=os.path.join(W,'kp_'+safe+'.json');side=os.path.join(W,'kpin_'+safe+'.meta.json')
    KPraw=read_json(kp,default=None);sc=read_json(side,default=None)
    ident=sc if isinstance(KPraw,dict) and '_meta' not in KPraw and isinstance(sc,dict) and os.path.getmtime(kp)>=os.path.getmtime(side) else None
    KP,kst,kmsg,stamp=check_kp(N,KPraw,ident,strict=bool(os.environ.get('WEIQI_STRICT')))
    if stamp:KPraw['_meta']=stamp;put(atomic_write_json,kp,KPraw,ensure_ascii=False)   # remember which tree the notes were written for
    if kst not in ('ok','missing'):log('B WARN',name,'key points:',kst,kmsg)
    rep['key_points']={'status':kst,'message':kmsg,'notes':len(KP)}
    if not os.path.exists(os.path.join(W,'fixdict.json')):log('B WARN',name,'no fixdict.json in',W,'- only the built in typo rules are used')
    sgf=merge(N,A,idxs,name,summ,KP)
    rep['key_points']['wanted']=len(DUMP)   # nodes with enough teacher text to deserve a note (the kpin dump)
    if len(DUMP) and len(KP)<0.5*len(DUMP):log('B WARN',name,'only',len(KP),'key point notes for',len(DUMP),'nodes that have teacher text - was the kp file written?')
    if isinstance(A.get('_meta'),dict) and A['_meta'].get('errors'):rep['analysis']['errors']=A['_meta']['errors'];log('B WARN',name,A['_meta']['errors'],'analysis queries returned an error')
    put(atomic_write_json,os.path.join(W,'fixlog_'+safe+'.json'),dict(FIRED.most_common()),ensure_ascii=False,indent=1)   # which typo rules fired, for review
    log('B typo rules fired',sum(FIRED.values()),'times; most used:',fixtext.top(FIRED));FIRED.clear()
    put(atomic_write_json,os.path.join(W,'kpin_'+safe+'.json'),DUMP[:],ensure_ascii=False);DUMP.clear()
    put(atomic_write_json,side,kp_ident(N))   # which tree this kpin dump describes (used to place the kp notes written from it)
    force=force or bool(os.environ.get('WEIQI_FORCE'))
    if dry:
        done,why=sgf_decision(sgf_path(name),sgf,force)
        log('DRY RUN',name,'-> would',('write' if done else 'REFUSE'),sgf_path(name),'| new',sgfcheck.metrics(sgf),'|','; '.join(why))
        return done
    done,why=write_sgf(sgf_path(name),sgf,force=force)
    if not done:   # keep the candidate so the work is not lost, and say loudly why the old file stays
        os.makedirs(os.path.join(W,'rejected'),exist_ok=True);atomic_write_text(os.path.join(W,'rejected',safe+'.sgf'),sgf)
        log('B REFUSED',name,'; '.join(why),'| existing SGF kept, candidate saved in',os.path.join(W,'rejected'),'| WEIQI_FORCE=1 overrides')
    rep['sgf']=dict(sgfcheck.metrics(sgf),written=done,reasons=why)
    atomic_write_json(os.path.join(W,'status_'+safe+'.json'),rep,ensure_ascii=False,indent=1)
    log('B done' if done else 'B NOT written',name,rep['nodes'],'nodes',len(sgf),'chars; analysis',st,'; key points',kst)
    return done
def run_pipeline(workers=2):
    G=groups()
    dur={x['idx']:x['sec'] for x in IDX if x['season']==SEASON}
    gp=sorted(G,key=lambda g:(g[0]!='小目-小飞挂-二间高夹',-sum(dur[i] for i in g[1])))   # 总时长长的优先
    order=[i for _,ix in gp for i in ix]
    ready={};ev=threading.Condition();built={}
    def runA(i):
        ok=False
        try:ok=process_video(i)
        finally:   # always report back, whatever happened, or stageB would wait for this video for ever
            with ev:ready[i]=int(ok);ev.notify_all()
    pool=ThreadPoolExecutor(workers)
    for i in order:pool.submit(runA,i)
    def build(name,idxs):
        use=[i for i in idxs if ready.get(i)]
        if not use:log('B skip',name,': no video of this group is ready');return
        if tuple(use)==built.get(name):return   # nothing new since the last build
        try:stageB(name,use,planned=idxs);built[name]=tuple(use)
        except Exception:log('B FAIL',name,traceback.format_exc()[-300:])
    for name,idxs in gp:
        with ev:
            while not all(i in ready for i in idxs):ev.wait(30)
        build(name,idxs)
    for rd in range(RETRY_ROUNDS):   # throttling usually clears: failed videos get another go after a pause, then their groups are rebuilt
        bad=[i for i in order if not ready.get(i)]
        if not bad:break
        log('retry round',rd+1,':',len(bad),'videos failed, waiting',RETRY_WAIT,'s');SLEEP(RETRY_WAIT)
        for i in bad:ready[i]=int(process_video(i))
        for name,idxs in gp:build(name,idxs)
    pool.shutdown()
    left=[i for i in order if not ready.get(i)]
    log('ALL DONE'+(' - videos still failing: %s, see %s'%(left,os.path.join(W,'failed_videos.json')) if left else ''))
    return built
if __name__=='__main__':
    setup_stdio()
    lock=None if os.environ.get('WEIQI_NO_LOCK') else single_instance(os.path.join(W,'orch2.lock'))   # held until the process ends
    if not os.environ.get('WEIQI_NO_LOCK') and lock is None:
        log('another orch2.py is already running (lock',os.path.join(W,'orch2.lock'),'), not starting a second one. WEIQI_NO_LOCK=1 skips this check.');sys.exit(1)
    run_pipeline()
