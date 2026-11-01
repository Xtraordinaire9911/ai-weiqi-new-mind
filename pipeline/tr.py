import sys,json,subprocess,numpy as np,glob,os
from faster_whisper import WhisperModel
ff=glob.glob(os.environ['LOCALAPPDATA']+r'\Microsoft\WinGet\Packages\Gyan.FFmpeg*\**\ffmpeg.exe',recursive=True)[0]
a=np.frombuffer(subprocess.run([ff,'-v','error','-i',sys.argv[1],'-ac','1','-ar','16000','-f','f32le','-'],capture_output=True).stdout,np.float32)
m=WhisperModel("small",device="cpu",compute_type="int8")
p="先手 后手 二间高夹 小目 小飞挂 飞压 冲断 白棋 黑棋 定式 AI 胜率 征子 一路 二路 三路"
seg,_=m.transcribe(a,language="zh",initial_prompt=p,vad_filter=True)
out=[{"s":round(x.start,1),"e":round(x.end,1),"t":x.text} for x in seg]
json.dump(out,open(sys.argv[2],"w",encoding="utf-8"),ensure_ascii=False);print(len(out))
