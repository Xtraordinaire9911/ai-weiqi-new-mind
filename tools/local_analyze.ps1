# 局部定式分析: 把 KataGo 的搜索/候选限制在指定矩形内(allowMoves)，并给出相对"局部最佳"的损失，而非全局胜率
# 用法: powershell -ExecutionPolicy Bypass -File tools/local_analyze.ps1 -Moves "B:qd,W:pf" -Region "11,0,18,8" -Visits 300 [-Next B]
# Region = xmin,ymin,xmax,ymax (SGF 坐标 a=0)。周围子力(征子/配置)通过 -Moves 里的额外棋子与 -Setup 传入，如 -Setup "B:dd,dp;W:pp"
param([string]$Moves="",[string]$Setup="",[string]$Region="0,0,18,18",[int]$Visits=300,[string]$Next="",[double]$Komi=6.5)
$root=Split-Path (Split-Path $PSScriptRoot); $E="$root\engine\katago-v1.18.0-opencl-windows-x64"
$gt=@('A','B','C','D','E','F','G','H','J','K','L','M','N','O','P','Q','R','S','T')
function G($s){ $gt[[int][char]$s[0]-97]+(19-([int][char]$s[1]-97)) }
$ini=@();foreach($grp in ($Setup -split ';'|?{$_})){$c,$l=$grp -split ':';foreach($p in $l -split ','){$ini+=,@($c,(G $p))}}
$mv=@();foreach($m in ($Moves -split ','|?{$_})){$c,$p=$m -split ':';$mv+=,@($c,(G $p))}
if(-not $Next){$Next= if($mv.Count -gt 0 -and $mv[-1][0] -eq 'B'){'W'}else{'B'}}
$r=$Region -split ',';$allow=@()
for($x=[int]$r[0];$x -le [int]$r[2];$x++){for($y=[int]$r[1];$y -le [int]$r[3];$y++){$allow+=(G ([string][char](97+$x)+[char](97+$y)))}}
$q=@{id='q';initialStones=$ini;moves=$mv;rules='japanese';komi=$Komi;boardXSize=19;boardYSize=19;analyzeTurns=@($mv.Count);maxVisits=$Visits;includeOwnership=$true
  allowMoves=@(@{player="B";moves=$allow;untilDepth=40},@{player="W";moves=$allow;untilDepth=40})}|ConvertTo-Json -Depth 6 -Compress
$q|Out-File "$env:TEMP\kq.json" -Encoding ascii
$out=Get-Content "$env:TEMP\kq.json"|& "$E\katago.exe" analysis -model "$root\weights\network_file\kata1-tf3-b11c768-s12752M-d6531M.bin.gz" -config "$E\analysis.cfg" 2>$null|Select-Object -First 1
$d=$out|ConvertFrom-Json;$mi=$d.moveInfos|sort order;$best=($mi|measure scoreLead -Maximum).Maximum
$mi|select -First 8|%{[pscustomobject]@{手=$_.move;访问=$_.visits;胜率=[math]::Round($_.winrate*100,1);目差=[math]::Round($_.scoreLead,1);相对局部最佳=[math]::Round($_.scoreLead-$best,1);先验=[math]::Round($_.prior*100,1);后续=($_.pv|select -First 6) -join ' '}}|ft -AutoSize
