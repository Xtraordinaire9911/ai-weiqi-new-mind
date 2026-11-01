<#
  Copy the generated data from the working clone into the local clone of the PRIVATE data repository and commit it there.
  Direction: working clone -> private clone. Nothing is ever written into the working clone, and nothing is pushed.

  Examples:
    powershell -ExecutionPolicy Bypass -File tools\sync_private_data.ps1 -DryRun    # show what would happen, change nothing
    powershell -ExecutionPolicy Bypass -File tools\sync_private_data.ps1            # copy and commit in the private clone
    powershell -ExecutionPolicy Bypass -File tools\sync_private_data.ps1 -NoCommit  # copy only
  Push by hand afterwards:  git -C <private clone> push

  What is copied (the same layout as the public repository):
    - data\sgf\**\*.sgf          the generated SGF files
    - data\library.js            the packed library
    - data\sources\**            plan.json and index.json of every source (the pipeline reads them)
    - pipeline\kp_*.json         key point notes, and pipeline\fixdict.json (typo list)
      The notes come from the working clone's pipeline folder and, when -WorkDir exists, from the pipeline work folder
      (the work folder wins when both have the file, because that is where the pipeline writes them).
  What is never done: deleting anything in the private clone (a file that disappears from the source stays in the
  private history), copying an empty or truncated file, writing into the source, pushing.
  A file that changes while it is being copied (the pipeline is writing it) is read again, up to 3 times, then skipped and listed.
#>
param(
  [string]$Source = (Split-Path $PSScriptRoot),                              # working clone with data\sgf and data\library.js
  [string]$Destination = 'D:\workspace\fun\Weiqi\ai-weiqi-new-mind-data',    # local clone of the private data repository
  [string]$WorkDir = 'D:\tmp\work',                                          # pipeline work folder (kp_*.json, fixdict.json); skipped when missing
  [string]$Message = 'chore: sync generated data',                           # commit subject
  [switch]$NoCommit,   # copy but do not commit
  [switch]$DryRun      # only print what would happen
)
$ErrorActionPreference = 'Stop'

function Fail($m) { Write-Error $m; exit 2 }
function Full($p) { [IO.Path]::GetFullPath($p).TrimEnd('\') }

# --- guards: wrong folders must be an error, never a silent "nothing to do" or a write into the wrong place ---
if (-not (Test-Path -LiteralPath (Join-Path $Source 'data\sgf') -PathType Container)) { Fail "Source has no data\sgf: $Source" }
if (-not (Test-Path -LiteralPath (Join-Path $Source 'data\library.js') -PathType Leaf)) { Fail "Source has no data\library.js: $Source" }
if (-not (Test-Path -LiteralPath (Join-Path $Destination '.git'))) { Fail "Destination is not a git clone: $Destination" }
$s = Full $Source; $d = Full $Destination
if ($s -eq $d -or $d.StartsWith($s + '\') -or $s.StartsWith($d + '\')) { Fail 'Source and Destination must be two separate folders.' }
$remote = (& git -C $Destination remote get-url origin 2>$null)
if ($remote -notmatch '-data(\.git)?$') { Fail "Destination remote does not look like the private data repository (expected a name ending in -data): $remote" }
if ($remote -match 'ai-weiqi-new-mind(\.git)?$') { Fail 'Destination is the PUBLIC repository. Refusing to copy the full data there.' }

$utf8 = New-Object Text.UTF8Encoding $false
$skipped = New-Object Collections.ArrayList
$script:copied = 0; $script:same = 0

function Sha($p) { (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash }

# Looks like a complete file? Cheap sanity checks so a half written file is not copied over a good one.
function Plausible($path) {
  $fi = Get-Item -LiteralPath $path
  if ($fi.Length -eq 0) { return 'empty' }
  if ($path -like '*.sgf') {
    $t = [IO.File]::ReadAllText($path, $utf8).TrimEnd()
    if (-not ($t.StartsWith('(;') -and $t.EndsWith(')'))) { return 'not a complete SGF' }
  }
  elseif ($path -like '*library.js') {
    $t = [IO.File]::ReadAllText($path, $utf8).TrimEnd()
    if (-not ($t.StartsWith('window.LIB=') -and $t.EndsWith(';'))) { return 'not a complete library.js' }
  }
  elseif ($path -like '*.json') {
    try { $null = [IO.File]::ReadAllText($path, $utf8) | ConvertFrom-Json } catch { return 'not valid JSON' }
  }
  return ''
}

function CopyOne($from, $to, $label) {
  if ((Test-Path -LiteralPath $to) -and ((Sha $from) -eq (Sha $to))) { $script:same++; return }
  for ($try = 1; $try -le 3; $try++) {
    $h1 = Sha $from
    $why = Plausible $from
    if ($why) { [void]$skipped.Add("$label ($why)"); return }
    if ($DryRun) { Write-Host "WOULD COPY   $label"; $script:copied++; return }
    $dir = Split-Path $to
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
    $tmp = $to + '.part'
    Copy-Item -LiteralPath $from -Destination $tmp -Force
    if ((Sha $tmp) -eq $h1 -and (Sha $from) -eq $h1) {
      Move-Item -LiteralPath $tmp -Destination $to -Force
      Write-Host "COPIED       $label"; $script:copied++; return
    }
    Remove-Item -LiteralPath $tmp -Force
    Start-Sleep -Seconds 2    # the source changed while copying: wait for the writer and read it again
  }
  [void]$skipped.Add("$label (kept changing while copying)")
}

# --- data\sgf, data\library.js, data\sources ---
foreach ($sub in @('data\sgf', 'data\sources')) {
  $root = Join-Path $Source $sub
  if (-not (Test-Path -LiteralPath $root)) { continue }
  Get-ChildItem -LiteralPath $root -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($s.Length + 1)
    CopyOne $_.FullName (Join-Path $Destination $rel) $rel
  }
}
CopyOne (Join-Path $Source 'data\library.js') (Join-Path $Destination 'data\library.js') 'data\library.js'

# --- key point notes and the typo list: clone first, then the work folder (it overrides) ---
$notes = @{}
foreach ($folder in @((Join-Path $Source 'pipeline'), $WorkDir)) {
  if (-not (Test-Path -LiteralPath $folder -PathType Container)) { continue }
  Get-ChildItem -LiteralPath $folder -File | Where-Object { $_.Name -like 'kp_*.json' -or $_.Name -eq 'fixdict.json' } |
    Where-Object { $_.Name -notmatch '^kp_\d+\.json$' } | ForEach-Object { $notes[$_.Name] = $_.FullName }   # kp_1.json ... are scratch dumps
}
foreach ($n in ($notes.Keys | Sort-Object)) {
  CopyOne $notes[$n] (Join-Path $Destination ('pipeline\' + $n)) ('pipeline\' + $n)
}

$verb = if ($DryRun) { 'would copy' } else { 'copied' }
Write-Host ""
Write-Host "$verb $script:copied file(s), $script:same already identical."
if ($skipped.Count) {
  Write-Host "SKIPPED $($skipped.Count) file(s) (nothing was changed for them):"
  $skipped | ForEach-Object { Write-Host "  $_" }
}

# --- commit in the private clone (never push) ---
if ($DryRun) { Write-Host 'Dry run: nothing written, nothing committed.'; exit 0 }
if ($NoCommit) { Write-Host 'Not committing (-NoCommit).'; exit 0 }
& git -C $Destination add -A
$changed = (& git -C $Destination status --porcelain)
if (-not $changed) { Write-Host 'Nothing new to commit.'; exit 0 }
& git -C $Destination commit -q -m $Message
if ($LASTEXITCODE -ne 0) { Fail 'git commit failed in the private clone.' }
Write-Host ("Committed in the private clone: " + (& git -C $Destination log --oneline -1))
Write-Host "Not pushed. Push by hand:  git -C `"$Destination`" push"
exit 0
