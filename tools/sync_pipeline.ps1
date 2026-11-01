# 把 D:\tmp\work 里的流水线脚本/词典/要点同步进仓库 pipeline/ (不含视频、转写、中间缓存)
$src='D:\tmp\work';$dst=Join-Path (Split-Path $PSScriptRoot) 'pipeline'
foreach($f in 'orch2.py','analyze2.py','board.py','tr.py','regen.py','serve.py','mkfix.py','fixdict.json'){Copy-Item "$src\$f" $dst -Force}
Get-ChildItem "$src\kp_*.json" | Copy-Item -Destination $dst -Force
