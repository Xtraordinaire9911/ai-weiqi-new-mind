import json,sys,subprocess,os,time,re
from treesync import make_meta   # records the tree fingerprint and the score perspective inside the output
from wqutil import atomic_write_json,read_json,setup_stdio   # atomic: a2.json existing must mean the analysis finished
setup_stdio()   # utf-8 log lines even on a cp936 console
# 用法: analyze2.py n.json out.json [主搜索visits=400] [强制评估visits=150]
# 修正: KataGo 配置 reportAnalysisWinratesAs=BLACK, 所有分数/胜率均为黑方视角 -> 这里统一转成"当前行棋方视角"(stm)
# KataGo location can be overridden by env (default: the original install)
root=os.environ.get('WEIQI_KATAGO_ROOT',r'D:\workspace\fun\Weiqi\Weiqi_AI');E=os.environ.get('WEIQI_KATAGO_DIR',os.path.join(root,'engine','katago-v1.18.0-opencl-windows-x64'))
MODEL=os.environ.get('WEIQI_KATAGO_MODEL',os.path.join(root,'weights','network_file','kata1-tf3-b11c768-s12752M-d6531M.bin.gz'))
N=read_json(sys.argv[1]);out=sys.argv[2]
VB=int(sys.argv[3]) if len(sys.argv)>3 else 220;VF=int(sys.argv[4]) if len(sys.argv)>4 else 100
LIMIT=int(os.environ.get('LIMIT','0'))
R=dict(x0=0,x1=10,y0=8,y1=18)
def region():   # 取本组变化树里所有落子坐标(去重)的 3%~97% 分位 + 2路余量, 靠近边线则贴边: 只在真正讲解的定式区域内搜索
    cs=set()
    for n in N:
        if n['dead']:continue
        if n['mv'] is not None:cs.add((n['mv'][0]%18,n['mv'][0]//18))
        elif n['par']==0:
            for t in re.findall(r'[BW]\d+',n['pos']):k=int(t[1:]);cs.add((k%18,k//18))
    xs=sorted(c for c,_ in cs);ys=sorted(r for _,r in cs)
    pc=lambda a,p:a[min(len(a)-1,int(len(a)*p))]
    x0=max(0,pc(xs,.03)-2);x1=min(17,pc(xs,.97)+2);y0=max(0,pc(ys,.03)-2);y1=min(18,pc(ys,.97)+2)
    if x0<=3:x0=0
    if y1>=15:y1=18
    if x1>=14:x1=17
    if y0<=3:y0=0
    return dict(x0=x0,x1=x1,y0=y0,y1=y1)
R=region();print('region',R,file=sys.stderr)
L='ABCDEFGHJKLMNOPQRST'
g=lambda c,r:L[c]+str(19-r)
def parse(pos):
    d={}
    for t in re.findall(r'[BW]\d+',pos):
        k=int(t[1:]);d[(k%18,k//18)]=t[0]
    return d
inreg=lambda c,r:R['x0']<=c<=R['x1'] and R['y0']<=r<=R['y1']
allow=[g(c,r) for c in range(R['x0'],R['x1']+1) for r in range(R['y0'],R['y1']+1)]
def path(i):
    p=[]
    while N[i]['mv'] is not None:p.append(i);i=N[i]['par']
    return i,p[::-1]
def stones(i):   # 该节点处全盘棋子集合(起始局面+着法), 用于判断区域外是否有子
    ri,p=path(i);d=dict(parse(N[ri]['pos']))
    for j in p:d[(N[j]['mv'][0]%18,N[j]['mv'][0]//18)]=N[j]['mv'][1]
    return d
def q(i,ctx,qid,visits):
    ri,p=path(i)
    ini=[[v,g(*k)] for k,v in parse(N[ri]['pos']).items() if ctx or inreg(*k)]
    mv=[[N[j]['mv'][1],g(N[j]['mv'][0]%18,N[j]['mv'][0]//18)] for j in p if (ctx or inreg(N[j]['mv'][0]%18,N[j]['mv'][0]//18))]
    return {'id':qid,'initialStones':ini,'moves':mv,'rules':'japanese','komi':6.5,'boardXSize':19,'boardYSize':19,'analyzeTurns':[len(mv)],'maxVisits':visits,
      'allowMoves':[{'player':'B','moves':allow,'untilDepth':40},{'player':'W','moves':allow,'untilDepth':40}]}
live=lambda i:[c for c in N[i]['ch'] if not N[c]['dead']]
todo=[i for i in range(len(N)) if not N[i]['dead'] and len(live(i))>=2]       # 只分析分支点(叶子/单链无意义)
rootkids=[i for i in range(len(N)) if not N[i]['dead'] and N[i]['setup'] and len(live(i))==1 and N[i]['par']==0]
todo=sorted(set(todo+rootkids))
if LIMIT:todo=todo[:LIMIT]
print('branch nodes',len(todo),file=sys.stderr)
p=subprocess.Popen([os.path.join(E,'katago.exe'),'analysis','-model',MODEL,'-config',os.path.join(E,'analysis.cfg')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=open(out+'.err','wb'),text=True,encoding='utf-8')
t0=time.time()
def run(reqs):
    for r in reqs:p.stdin.write(json.dumps(r)+'\n')
    p.stdin.flush();res={}
    for _ in reqs:
        d=json.loads(p.stdout.readline())
        if 'moveInfos' not in d:res[d['id']]={'err':str(d)[:120]};continue
        t=d['rootInfo']['currentPlayer'];sg=1 if t=='B' else -1
        mi=sorted(d['moveInfos'],key=lambda m:m['order'])
        res[d['id']]={'turn':t,'score':round(sg*d['rootInfo']['scoreLead'],1),'wr':round(d['rootInfo']['winrate'] if t=='B' else 1-d['rootInfo']['winrate'],3),
         'cand':[{'m':m['move'],'v':m['visits'],'s':round(sg*m['scoreLead'],1),'wr':round(m['winrate'] if t=='B' else 1-m['winrate'],3),'p':round(m['prior'],3),'pv':m['pv'][:8]} for m in mi[:14]]}
        print(len(res),len(reqs),round(time.time()-t0),file=sys.stderr)
    return res
res={}
# 阶段1: 分支点主搜索 (区域外有子时另做一次"去掉区域外子力"对照)
reqs=[]
for i in todo:
    reqs.append(q(i,True,'%d'%i,VB))
    st=stones(i)
    if any(not inreg(*k) for k in st):reqs.append(q(i,False,'%d_0'%i,min(VB,200)))
res.update(run(reqs))
# 阶段2: 老师走的每一手若AI搜索没给出可信访问量, 单独强制评估(走完这手后的局面, 对方视角取反)
reqs=[];need=[]
for i in todo:
    a=res.get('%d'%i)
    if not a or 'cand' not in a:continue
    tv=max(m['v'] for m in a['cand'])
    for c in live(i):
        if N[c]['mv'] is None:continue
        m=g(N[c]['mv'][0]%18,N[c]['mv'][0]//18)
        cm=next((x for x in a['cand'] if x['m']==m),None)
        if cm and cm['v']>=max(10,.1*tv):continue
        if m not in allow:continue          # 区域外着法(脱先等): 不评估
        reqs.append(q(c,True,'f%d'%c,VF));need.append((i,c,m))
fr=run(reqs) if reqs else {}
for i,c,m in need:
    f=fr.get('f%d'%c);a=res['%d'%i]
    if not f or 'cand' not in f or not f['cand']:continue
    t=f['cand'][0]
    a['cand'].append({'m':m,'v':VF,'s':round(-f['score'],1),'wr':round(1-f['wr'],3),'p':-1,'pv':[m]+t['pv'][:7],'f':1})
p.stdin.close();res['_meta']=make_meta(N,visits=[VB,VF],region=R,complete=not LIMIT);atomic_write_json(out,res);print('done',round(time.time()-t0),file=sys.stderr)
