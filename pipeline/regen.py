import sys,os,re;sys.argv=['x'];import orch2 as o
for name,idxs in o.groups():
    safe=re.sub(r'[\\/:*?"<>|]','',name)
    if not os.path.exists(os.path.join(o.W,'g_'+safe+'.a.json')):continue
    ix=[i for i in idxs if os.path.exists(os.path.join(o.D(i),'b.json'))]
    o.stageB(name,ix)
