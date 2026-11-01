# Usage: pwsh tools/fetch_playlists.ps1 -Mid 160181458 -Seasons 2020332,1500387,249748 -Out data/sources/chenlintao/index.json
param([string]$Mid,[string[]]$Seasons,[string]$Out)
$h=@{'User-Agent'='Mozilla/5.0';Referer='https://www.bilibili.com'}
$all=@()
foreach($s in $Seasons){
  $d=(Invoke-RestMethod -Headers $h "https://api.bilibili.com/x/polymer/web-space/seasons_archives_list?mid=$Mid&season_id=$s&page_num=1&page_size=100").data
  $i=0
  foreach($a in $d.archives){$i++; $all+=[pscustomobject]@{season=[int]$s;seasonName=$d.meta.name;idx=$i;bvid=$a.bvid;title=$a.title;sec=$a.duration;sgf=$null}}
}
$all|ConvertTo-Json -Depth 4|Set-Content -Encoding utf8 $Out
$all|Group-Object season|%{"$($_.Name) $($_.Group[0].seasonName): $($_.Count)"}

