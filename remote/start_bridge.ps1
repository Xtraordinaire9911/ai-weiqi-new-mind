# start_bridge.ps1 -- starts remote\katago_bridge.py with the KataGo binary and network found on this machine (Windows).
# It only looks at a few usual places on THIS computer and starts the bridge on 127.0.0.1. Nothing is downloaded, installed or sent anywhere.
#
#   powershell -ExecutionPolicy Bypass -File remote\start_bridge.ps1                  find KataGo and a network, start the bridge on port 8787
#   powershell -ExecutionPolicy Bypass -File remote\start_bridge.ps1 -PrintSetup      print what you must provide, then exit
#   ... -Katago C:\katago\katago.exe -Model C:\katago\kata1-xxx.bin.gz [-Config C:\katago\analysis.cfg] [-Port 8787]
#   ... -Fake                                                                         no KataGo at all, simulated data (to try the page)
#   ... -ExtraArgs '--allow-origin','https://example.org'                             passed on to katago_bridge.py
#
# Environment: KATAGO_BIN, KATAGO_MODEL, KATAGO_CONFIG, KATAGO_MODELS_DIR, KATAGO_BRIDGE_TOKEN (a random token is printed once when unset).
param(
  [string]$Katago = $env:KATAGO_BIN,
  [string]$Model = $env:KATAGO_MODEL,
  [string]$Config = $env:KATAGO_CONFIG,
  [int]$Port = 8787,
  [switch]$Fake,
  [switch]$PrintSetup,
  [string[]]$ExtraArgs = @()
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $here 'katago_bridge.py'

# ---- find Python 3.8+ (the "python" stub of the Microsoft Store does not count)
$py = $null
foreach ($c in @(@('py', '-3'), @('python'), @('python3'))) {
  $exe = Get-Command $c[0] -ErrorAction SilentlyContinue
  if (-not $exe) { continue }
  $pre = @(); if ($c.Count -gt 1) { $pre = $c[1..($c.Count - 1)] }
  try {
    & $exe.Source @pre -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) { $py = @($exe.Source) + $pre; break }
  } catch { }
}
if (-not $py) { [Console]::Error.WriteLine('Python 3.8 or newer is needed (the bridge uses only its standard library).'); exit 2 }
function Run-Bridge([string[]]$bridgeArgs) {
  & $py[0] @($py[1..($py.Count)] | Where-Object { $_ }) $script @bridgeArgs
  exit $LASTEXITCODE
}
if ($PrintSetup) { Run-Bridge @('--print-setup') }
if ($Fake) { Run-Bridge (@('--fake', '--port', "$Port") + $ExtraArgs) }

# ---- find the KataGo binary
if (-not $Katago) {
  $cands = @()
  $cmd = Get-Command katago.exe -ErrorAction SilentlyContinue
  if ($cmd) { $cands += $cmd.Source }
  $cands += 'C:\katago\katago.exe', (Join-Path $env:USERPROFILE 'katago\katago.exe'), (Join-Path $env:LOCALAPPDATA 'katago\katago.exe'),
            'C:\Program Files\KataGo\katago.exe', (Join-Path $env:USERPROFILE 'scoop\apps\katago\current\katago.exe')
  $cands += @(Get-ChildItem (Join-Path $env:USERPROFILE 'katago*\katago.exe'), (Join-Path $env:USERPROFILE 'Downloads\katago*\katago.exe') -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
  foreach ($c in $cands) { if ($c -and (Test-Path -LiteralPath $c -PathType Leaf)) { $Katago = $c; break } }
}
# ---- find a network (newest .bin.gz in the usual places)
if (-not $Model) {
  $dirs = @()
  if ($env:KATAGO_MODELS_DIR) { $dirs += $env:KATAGO_MODELS_DIR }
  if ($Katago) { $bd = Split-Path -Parent $Katago; $dirs += $bd, (Join-Path $bd 'models') }
  $dirs += (Join-Path $env:USERPROFILE 'katago'), (Join-Path $env:USERPROFILE 'katago\models'), (Join-Path $env:USERPROFILE '.katago'), (Join-Path $env:USERPROFILE 'Downloads'), 'C:\katago', 'C:\katago\models'
  foreach ($d in $dirs) {
    if (-not (Test-Path -LiteralPath $d -PathType Container)) { continue }
    $f = Get-ChildItem -LiteralPath $d -Filter '*.bin.gz' -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($f) { $Model = $f.FullName; break }
  }
}
$miss = $false
if (-not $Katago -or -not (Test-Path -LiteralPath $Katago -PathType Leaf)) { Write-Host 'KataGo executable not found. Give it with -Katago PATH or KATAGO_BIN.'; $miss = $true }
if (-not $Model -or -not (Test-Path -LiteralPath $Model -PathType Leaf)) { Write-Host 'Network file (.bin.gz) not found. Give it with -Model PATH or KATAGO_MODEL.'; $miss = $true }
if ($miss) { Write-Host ''; & $py[0] @($py[1..($py.Count)] | Where-Object { $_ }) $script --print-setup; exit 2 }

Write-Host "KataGo : $Katago"
Write-Host "Network: $Model"
$a = @('--katago', $Katago, '--model', $Model, '--models-dir', (Split-Path -Parent $Model), '--port', "$Port")
if ($Config) { Write-Host "Config : $Config"; $a += @('--config', $Config) }
Run-Bridge ($a + $ExtraArgs)
