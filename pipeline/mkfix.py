import json
D=[('搬','扳'),('班','扳'),('联班','连扳'),('连班','连扳'),('联扳','连扳'),('骑行','棋形'),('关子','官子'),('沾','粘'),('针子','征子'),('争死','征子'),('雾开','五五开'),('定时','定式'),('续盘','序盘'),('局务','局部'),('米是飞刀','米式飞刀'),('煎三三','点三三'),('煎充','尖冲'),('煎','尖'),('拖鞋','脱先'),('脱鞋','脱先'),('讲碑','讲碰'),('老定势','老定式')]
json.dump(D,open('fixdict.json','w',encoding='utf-8'),ensure_ascii=False)
s=open('orch2.py',encoding='utf-8').read()
a=s.index("def fix(t):");b=s.index("def mm(")
new='''def fix(t):
    try:DD=[tuple(x) for x in json.load(open(os.path.join(W,'fixdict.json'),encoding='utf-8'))]
    except Exception:DD=[]
    for a,b in sorted(FIX+DD,key=lambda x:-len(x[0])):t=t.replace(a,b)
    return t.replace('拖延','\x00').replace('拖','托').replace('\x00','拖延')
'''
s=s[:a]+new+s[b:]
s=s.replace("txt+='【要点与考量】'+KP[str(k)]+chr(10)","txt+='【要点与考量】'+fix(KP[str(k)])+chr(10)")
open('orch2.py','w',encoding='utf-8').write(s)
