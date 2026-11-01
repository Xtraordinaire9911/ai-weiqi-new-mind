# 1) 为每个 source 的 plan 生成/补全 SGF 骨架(不覆盖已有内容)  2) 打包 data/library.js 供 index.html 离线读取
# 用法: powershell -ExecutionPolicy Bypass -File tools/build.ps1
$root=Split-Path $PSScriptRoot; $u=New-Object Text.UTF8Encoding $false
function Clean($s){ ($s -replace '[\/:*?"<>|？！，：。“”、…\s]+','') }
$cols=@()
# Credit header for every generated SGF root: AP (application), CP (copyright and license line) and SO (source), so the credit travels with the file. Keep the wording in sync with NOTICE.md and pipeline/orch2.py.
function EscSgf($s){ ($s -replace '\\','\\' -replace '\]','\]') }   # ] and \ must be escaped inside a property value
$repoUrl='https://github.com/Xtraordinaire9911/ai-weiqi-new-mind'
$ver=if(Test-Path "$root\VERSION"){(Get-Content -Raw "$root\VERSION").Trim()}else{'unknown'}
$creditCp="Based on ai-weiqi-new-mind by Xtraordinaire9911 ($repoUrl), licensed under PolyForm Noncommercial 1.0.0 (code) and CC BY-NC-SA 4.0 (data and docs). The teacher commentary text belongs to 陈林涛 and is not covered by these licenses."
$credit="AP[$(EscSgf "ai-weiqi-new-mind:$ver")]CP[$(EscSgf $creditCp)]SO[$(EscSgf $repoUrl)]"
foreach($sd in Get-ChildItem "$root\data\sources" -Directory){
  $plan=Get-Content -Raw -Encoding utf8 "$($sd.FullName)\plan.json"|ConvertFrom-Json
  $idx=Get-Content -Raw -Encoding utf8 "$($sd.FullName)\index.json"|ConvertFrom-Json
  $groups=@()
  foreach($sn in $plan.series.PSObject.Properties.Name){
    $sv=$idx|?{$_.season -eq [int]$sn}
    $m=$plan.merge.$sn
    if($m){ foreach($g in $m){ $groups+=[pscustomobject]@{ser=$sn;name=$g[0];vids=@($g[1]|%{$i=$_;$sv|?{$_.idx -eq $i}})} } }
    else { foreach($v in $sv){ $groups+=[pscustomobject]@{ser=$sn;name=('{0}-{1:00}-{2}' -f $plan.series.$sn,$v.idx,(Clean $v.title));vids=@($v)} } }
  }
  foreach($g in $groups){
    $dir="$root\data\sgf\$($sd.Name)\$($plan.series.($g.ser))"; New-Item -ItemType Directory -Force $dir|Out-Null
    $f="$dir\$($g.name).sgf"
    if(-not (Test-Path $f)){
      $c=($g.vids|%{"$($_.bvid) $($_.title)"}) -join "`n"
      [IO.File]::WriteAllText($f,"(;GM[1]FF[4]CA[UTF-8]SZ[19]KM[6.5]GN[$($g.name)]PC[$($plan.name)]$($credit)C[来源视频:`n$c`n`n(待填充: 变化分支 + 口述解析; 解析写在各节点C[]里, 可用 @mm:ss 标注视频时间点)])",$u)
    }
    $cols+=[pscustomobject]@{id="$($sd.Name)/$($plan.series.($g.ser))/$($g.name)";source=$sd.Name;sourceName=$plan.name;series=$plan.series.($g.ser);name=$g.name;videos=@($g.vids|%{@{bvid=$_.bvid;title=$_.title}});sgf=[IO.File]::ReadAllText($f)}
  }
}
[IO.File]::WriteAllText("$root\data\library.js","window.LIB="+($cols|ConvertTo-Json -Depth 5 -Compress)+";window.LIBT='"+(Get-Date -Format 'MM-dd HH:mm')+"';",$u)
"collections: $($cols.Count)"
