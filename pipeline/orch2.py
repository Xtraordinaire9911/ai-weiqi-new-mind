# 无人值守流水线: 视频(下载->转写->识谱) -> 按SGF分组合并树 -> KataGo局部分析 -> 合成带解析SGF
import json,os,sys,subprocess,glob,re,threading,time,traceback
from concurrent.futures import ThreadPoolExecutor
W=r'D:\tmp\work';V=r'D:\tmp\vid';PROJ=r'D:\workspace\fun\Weiqi\Weiqi_AI\josekiapp'
PY=os.environ['LOCALAPPDATA']+r'\Programs\Python\Python312\python.exe'
FF=glob.glob(os.environ['LOCALAPPDATA']+r'\Microsoft\WinGet\Packages\Gyan.FFmpeg*\**\ffmpeg.exe',recursive=True)[0]
IDX=json.load(open(PROJ+r'\data\sources\chenlintao\index.json',encoding='utf-8-sig'))
PLAN=json.load(open(PROJ+r'\data\sources\chenlintao\plan.json',encoding='utf-8-sig'))
DL=threading.Semaphore(1)
log=lambda *a:print(time.strftime('%H:%M:%S'),*a,flush=True)
vid={x['idx']:x for x in IDX if x['season']==1500387}
def D(i):return os.path.join(W,'v',str(i));
# ---- 阶段A: 单视频 ----
def stageA(i):
    os.makedirs(D(i),exist_ok=True);b=vid[i]['bvid'];mp4=D(i)+r'\v.mp4'
    if not os.path.exists(mp4):
        with DL:
            for k in range(40):
                subprocess.run([PY,'-m','yt_dlp','-f','bv*[height<=720][vcodec^=avc]+ba/b[height<=720]/b','--merge-output-format','mp4','--ffmpeg-location',os.path.dirname(FF),'--retries','10','-N','1','--sleep-requests','1','-o',mp4,'https://www.bilibili.com/video/'+b],capture_output=True)
                if os.path.exists(mp4) and os.path.getsize(mp4)>1e6:break
                time.sleep(45)
            else:raise RuntimeError('download failed %d'%i)
    if not os.path.exists(D(i)+r'\t.json'):subprocess.run([PY,W+r'\tr.py',mp4,D(i)+r'\t.json'],check=True,capture_output=True)
    if not os.path.exists(D(i)+r'\b.json'):subprocess.run([PY,W+r'\board.py',mp4,D(i)+r'\b.json',FF],check=True,capture_output=True)
    log('A done',i,vid[i]['title'])
# ---- 分组树 (多视频合并) ----
C=18;DT=1/6
def build_tree(vids):
    st=lambda s:frozenset((i,ch) for i,ch in enumerate(s) if ch!='.')
    nodes=[{'pos':frozenset(),'par':None,'mv':None,'v':[],'ch':[],'setup':False}];index={frozenset():0}
    def new(pos,par,mv,t,vi,setup=False):
        nodes.append({'pos':pos,'par':par,'mv':mv,'v':[[t,t+DT,vi]],'ch':[],'setup':setup});nodes[par]['ch'].append(len(nodes)-1);return len(nodes)-1
    for vi,i in enumerate(vids):
        fr=json.load(open(D(i)+r'\b.json'));cur=None;prevs=None
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
DUMP=[]
# Credit header for every generated SGF root: AP (application), CP (copyright and license line) and SO (source), so the credit travels with the file. Keep the wording in sync with NOTICE.md and tools/build.ps1.
REPO_URL='https://github.com/Xtraordinaire9911/ai-weiqi-new-mind'
CREDIT_CP='Based on ai-weiqi-new-mind by Xtraordinaire9911 ('+REPO_URL+'), licensed under PolyForm Noncommercial 1.0.0 (code) and CC BY-NC-SA 4.0 (data and docs). The teacher commentary text belongs to 陈林涛 and is not covered by these licenses.'
def credit_props():
    try:ver=open(os.path.join(PROJ,'VERSION'),encoding='utf-8').read().strip()
    except OSError:ver='unknown'
    return 'AP[%s]CP[%s]SO[%s]'%(esc('ai-weiqi-new-mind:'+ver),esc(CREDIT_CP),esc(REPO_URL))
def merge(N,A,vids,name,summ='',KP={}):
    T=[json.load(open(D(i)+r'\t.json',encoding='utf-8')) for i in vids]
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
        c0=a['cand'];srch=[m for m in c0 if not m.get('f')];tv=max([m['v'] for m in srch] or [1])
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
    return '(;GM[1]FF[4]CA[UTF-8]SZ[19]KM[6.5]GN[%s]PC[陈林涛 %s]%s%s)'%(name,' '.join(vid[i]['bvid'] for i in vids),credit_props(),node(0))
# ---- 阶段B: 分组 ----
def groups():
    out=[]
    for name,idxs in PLAN['merge']['1500387']:
        if any(x>49 for x in idxs):continue
        out.append((name,idxs))
    return out
def stageB(name,idxs,visits=150):
    safe=re.sub(r'[\\/:*?"<>|]','',name);base=os.path.join(W,'g_'+safe)
    N=build_tree(idxs);json.dump(N,open(base+'.n.json','w'))
    a2=base+'.a2.json'
    if not os.path.exists(a2) and not os.environ.get('NOAN'):
        subprocess.run([PY,W+r'\analyze2.py',base+'.n.json',a2,'220','100'],capture_output=True)
    A=json.load(open(a2)) if os.path.exists(a2) else {}
    summ=open(W+r'\summary_%s.md'%safe,encoding='utf-8').read() if os.path.exists(W+r'\summary_%s.md'%safe) else ''
    kp=os.path.join(W,'kp_'+safe+'.json');KP=json.load(open(kp,encoding='utf-8')) if os.path.exists(kp) else {}
    sgf=merge(N,A,idxs,name,summ,KP)
    json.dump(DUMP[:],open(os.path.join(W,'kpin_'+safe+'.json'),'w',encoding='utf-8'),ensure_ascii=False);DUMP.clear()
    open(PROJ+r'\data\sgf\chenlintao\定式大全\%s.sgf'%name,'w',encoding='utf-8').write(sgf)
    log('B done',name,sum(1 for n in N if not n['dead']),'nodes',len(sgf))
if __name__=='__main__':
    G=groups();need=sorted({i for _,ix in G for i in ix},key=lambda i:-IDXDUR.get(i,0)) if False else None
    dur={x['idx']:x['sec'] for x in IDX if x['season']==1500387}
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
