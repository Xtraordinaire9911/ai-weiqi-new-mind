import sys,json,subprocess,numpy as np,glob,os
from wqutil import atomic_write_json,find_ffmpeg,setup_stdio   # atomic: t.json existing must mean it is complete
setup_stdio()
ff=find_ffmpeg()
if not ff:sys.exit('ffmpeg not found (set FFMPEG=path)')
from faster_whisper import WhisperModel
a=np.frombuffer(subprocess.run([ff,'-v','error','-i',sys.argv[1],'-ac','1','-ar','16000','-f','f32le','-'],capture_output=True).stdout,np.float32)
m=WhisperModel("small",device="cpu",compute_type="int8")
p="先手 后手 二间高夹 小目 小飞挂 飞压 冲断 白棋 黑棋 定式 AI 胜率 征子 一路 二路 三路"
seg,_=m.transcribe(a,language="zh",initial_prompt=p,vad_filter=True)
out=[{"s":round(x.start,1),"e":round(x.end,1),"t":x.text} for x in seg]
atomic_write_json(sys.argv[2],out,ensure_ascii=False);print(len(out))
