# 无人值守流水线: 视频(下载->转写->识谱) -> 按SGF分组合并树 -> KataGo局部分析 -> 合成带解析SGF
import json,os,sys,subprocess,glob,re,threading,time,traceback
from concurrent.futures import ThreadPoolExecutor
from treesync import tree_fingerprint,check_analysis,check_kp,kp_ident,USABLE
import sgfcheck
from wqutil import atomic_write_json,atomic_write_text,read_json,find_ffmpeg,setup_stdio,utf8_env,Log   # atomic outputs: a kill mid-write must not leave partial files
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
def stageA(i):
    if not FF:raise RuntimeError('ffmpeg not found (set FFMPEG=path)')
    os.makedirs(D(i),exist_ok=True);b=vid[i]['bvid'];mp4=os.path.join(D(i),'v.mp4');tj=os.path.join(D(i),'t.json');bj=os.path.join(D(i),'b.json')
    if not os.path.exists(mp4):
        with DL:
            for k in range(40):
                subprocess.run([PY,'-m','yt_dlp','-f','bv*[height<=720][vcodec^=avc]+ba/b[height<=720]/b','--merge-output-format','mp4','--ffmpeg-location',os.path.dirname(FF),'--retries','10','-N','1','--sleep-requests','1','-o',mp4,'https://www.bilibili.com/video/'+b],capture_output=True,env=ENV)
                if os.path.exists(mp4) and os.path.getsize(mp4)>1e6:break
                time.sleep(45)
            else:raise RuntimeError('download failed %d'%i)
    if not os.path.exists(tj):subprocess.run([PY,os.path.join(HERE,'tr.py'),mp4,tj],check=True,capture_output=True,env=ENV)
    if not os.path.exists(bj):subprocess.run([PY,os.path.join(HERE,'board.py'),mp4,bj,FF],check=True,capture_output=True,env=ENV)
    log('A done',i,vid[i]['title'])
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
FIX=[('黑旗','黑棋'),('白旗','白棋'),('黑鸡','黑棋'),('白鸡','白棋'),('拖鲜','脱先'),('脱鲜','脱先'),('拖先','脱先'),('争子','征子'),('正子','征子'),('结材','劫材'),('新位','星位'),('小木','小目'),('一肩','一间'),('拖角','托角'),('拖脚','托角'),('煎顶','尖顶'),('二肩','二间'),('小煎','小尖'),('煎冲','尖冲'),('加击','夹击'),('高加','高夹'),('低加','低夹'),('斑','扳'),('棋型','棋形')]
def fix(t):
    try:DD=[tuple(x) for x in json.load(open(os.path.join(W,'fixdict.json'),encoding='utf-8'))]
    except Exception:DD=[]
    for a,b in sorted(FIX+DD,key=lambda x:-len(x[0])):t=t.replace(a,b)
    return t.replace('拖延','@@').replace('拖','托').replace('@@','拖延')
def mm(vi,t):return '@%d|%d:%02d'%(vi,t//60,t%60)
def esc(s):return s.replace('\\','\\\\').replace(']','\\]')
def clean_cands(cs):   # keep candidates whose move is a board coordinate; 'pass' or garbage would put an invalid entry into AN[]
    return [dict(m,pv=[x for x in m['pv'] if sgfcheck.GTP.fullmatch(x)]) for m in cs if sgfcheck.GTP.fullmatch(m['m'])]
DUMP=[]
def merge(N,A,vids,name,summ='',KP={}):
    DUMP.clear()   # a failed merge of an earlier group must not leak its nodes into this group's kpin dump
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
def groups():
    if SRC_ERR:raise RuntimeError('cannot read index.json/plan.json: '+SRC_ERR)
    out=[]
    for name,idxs in PLAN['merge'][str(SEASON)]:
        if any(x>MAXIDX for x in idxs):continue
        out.append((name,idxs))
    return out
def write_sgf(path,sgf,force=False):
    """Write sgf unless it is invalid or poorer than the file already there (fewer nodes, less AI data or notes). Returns (written, reasons)."""
    bad=sgfcheck.validate(sgf)
    if bad:return False,['new sgf is invalid: '+'; '.join(bad[:3])]
    if not os.path.isdir(os.path.dirname(path)):return False,['target folder does not exist: '+os.path.dirname(path)]   # a wrong path must not create stray files
    if os.path.exists(path) and not force:
        with open(path,encoding='utf-8-sig') as f:old=f.read()
        if not sgfcheck.validate(old):   # a damaged old file may be replaced, a good one only by an equal or richer one
            why=sgfcheck.worse(sgfcheck.metrics(sgf),sgfcheck.metrics(old))
            if why:return False,['would lose data: '+', '.join(why)]
    atomic_write_text(path,sgf);return True,[]
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
def stageB(name,idxs,visits=150,force=False):
    safe=safe_name(name);base=os.path.join(W,'g_'+safe)
    rep={'group':name,'videos':list(idxs),'time':time.strftime('%Y-%m-%d %H:%M:%S')}   # one status record per group, see status_<group>.json
    N=build_tree(idxs);fp=tree_fingerprint(N);atomic_write_json(base+'.n.json',N)
    rep.update(tree_fp=fp,nodes=sum(1 for n in N if not n['dead']))
    # --- analysis: it must belong to exactly this tree, otherwise redo it (or leave the AI part out); never merge a mismatch
    a2=base+'.a2.json'
    A=read_json(a2,default=None);st,msg=check_analysis(N,A)   # explicit utf-8; a damaged file reads as missing
    if st not in USABLE and not os.environ.get('NOAN'):
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
    if stamp:KPraw['_meta']=stamp;atomic_write_json(kp,KPraw,ensure_ascii=False)   # remember which tree the notes were written for
    if kst not in ('ok','missing'):log('B WARN',name,'key points:',kst,kmsg)
    rep['key_points']={'status':kst,'message':kmsg,'notes':len(KP)}
    sgf=merge(N,A,idxs,name,summ,KP)
    atomic_write_json(os.path.join(W,'kpin_'+safe+'.json'),DUMP[:],ensure_ascii=False);DUMP.clear()
    atomic_write_json(side,kp_ident(N))   # which tree this kpin dump describes (used to place the kp notes written from it)
    done,why=write_sgf(sgf_path(name),sgf,force=force or bool(os.environ.get('WEIQI_FORCE')))
    if not done:   # keep the candidate so the work is not lost, and say loudly why the old file stays
        os.makedirs(os.path.join(W,'rejected'),exist_ok=True);atomic_write_text(os.path.join(W,'rejected',safe+'.sgf'),sgf)
        log('B REFUSED',name,'; '.join(why),'| existing SGF kept, candidate saved in',os.path.join(W,'rejected'),'| WEIQI_FORCE=1 overrides')
    rep['sgf']=dict(sgfcheck.metrics(sgf),written=done,reasons=why)
    atomic_write_json(os.path.join(W,'status_'+safe+'.json'),rep,ensure_ascii=False,indent=1)
    log('B done' if done else 'B NOT written',name,rep['nodes'],'nodes',len(sgf),'chars; analysis',st,'; key points',kst)
if __name__=='__main__':
    setup_stdio()
    G=groups()
    dur={x['idx']:x['sec'] for x in IDX if x['season']==SEASON}
    gp=sorted(G,key=lambda g:(g[0]!='小目-小飞挂-二间高夹',-sum(dur[i] for i in g[1])))   # 总时长长的优先
    order=[i for _,ix in gp for i in ix]
    ready={};ev=threading.Condition()
    def runA(i):
        try:stageA(i);ok=1
        except Exception as e:log('A FAIL',i,e);ok=0
        with ev:ready[i]=ok;ev.notify_all()
    pool=ThreadPoolExecutor(2)
    for i in order:pool.submit(runA,i)
    for name,idxs in gp:
        with ev:
            while not all(i in ready for i in idxs):ev.wait(30)
        idxs=[i for i in idxs if ready[i]]
        if not idxs:continue
        try:stageB(name,idxs)
        except Exception as e:log('B FAIL',name,traceback.format_exc()[-300:])
    log('ALL DONE')
