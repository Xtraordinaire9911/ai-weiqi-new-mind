import sys,json,subprocess,numpy as np
from wqutil import atomic_write_json   # atomic: b.json existing must mean it is complete
W,H=1134,720;X0,Y0,D=248.0,40.0,35.4
ff=sys.argv[3]
cmd=[ff,'-v','error','-i',sys.argv[1],'-vf','fps=6,scale=1134:720','-f','rawvideo','-pix_fmt','rgb24','-']
p=subprocess.Popen(cmd,stdout=subprocess.PIPE)
ang=np.linspace(0,2*np.pi,8,endpoint=False);ox=(9*np.cos(ang)).round().astype(int);oy=(9*np.sin(ang)).round().astype(int)
pts=[(c,r,int(round(X0+D*c)),int(round(Y0+D*r))) for r in range(19) for c in range(18)]
def read(f):
    s=''
    for c,r,x,y in pts:
        v=f[y+oy,x+ox].astype(int);lum=np.median(v.sum(1)/3);sat=np.median(v.max(1)-v.min(1))
        s+= 'B' if lum<75 else ('W' if lum>185 and sat<45 else '.')
    return s
out=[];i=0
while True:
    b=p.stdout.read(W*H*3)
    if len(b)<W*H*3:break
    f=np.frombuffer(b,np.uint8).reshape(H,W,3)
    ok=abs(int(f[200,300,0])-225)<40 and abs(int(f[200,300,2])-85)<60   # 棋盘底色检测
    out.append([i/6,read(f) if ok else None]);i+=1
atomic_write_json(sys.argv[2],out)
print(len(out),sum(1 for o in out if o[1]))
