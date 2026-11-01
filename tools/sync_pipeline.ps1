<#
  Copy the pipeline scripts from the work folder (where the pipeline runs) into the repo's pipeline/ folder.
  Direction: work folder -> repo. Nothing is ever copied the other way.

  Examples:
    powershell -ExecutionPolicy Bypass -File tools\sync_pipeline.ps1 -DryRun     # show what would happen, copy nothing
    powershell -ExecutionPolicy Bypass -File tools\sync_pipeline.ps1             # copy, but never over a newer repo file
    powershell -ExecutionPolicy Bypass -File tools\sync_pipeline.ps1 -Force      # copy even over newer repo files

  What is copied:
    - every *.py file and fixdict.json that exists in BOTH folders (so new modules such as wqutil.py or wq.py are picked
      up without editing this script),
    - kp_*.json key point notes from the work folder (they may be new),
    - never videos, transcripts, caches or logs.
  What is not copied: a file that is identical, a file that is newer in the repo (unless -Force), an empty file.
  Scripts that only exist in the work folder are listed at the end so you notice them.
#>
param(
  [string]$Source = 'D:\tmp\work',                                            # work folder the pipeline runs in
  [string]$Destination = (Join-Path (Split-Path $PSScriptRoot) 'pipeline'),    # repo pipeline/ folder
  [switch]$Force,    # also overwrite files that are newer in the repo
  [switch]$DryRun    # only print what would happen
)
$ErrorActionPreference = 'Stop'

# A wrong folder must be an error, not a silent "nothing to do".
if (-not (Test-Path -LiteralPath $Source -PathType Container)) { Write-Error "Source folder not found: $Source" }
if (-not (Test-Path -LiteralPath $Destination -PathType Container)) { Write-Error "Destination folder not found: $Destination" }

# Candidates: what the repo already has (*.py and the typo dictionary) plus the key point notes of the work folder.
$names = @(Get-ChildItem -LiteralPath $Destination -File |
    Where-Object { $_.Extension -eq '.py' -or $_.Name -eq 'fixdict.json' } | ForEach-Object { $_.Name })
$names += @(Get-ChildItem -LiteralPath $Source -File -Filter 'kp_*.json' | ForEach-Object { $_.Name })
$names = @($names | Sort-Object -Unique)

$copied = 0; $same = 0; $newer = 0; $empty = 0; $missing = 0
foreach ($n in $names) {
  $s = Join-Path $Source $n
  $d = Join-Path $Destination $n
  if (-not (Test-Path -LiteralPath $s)) { $missing++; continue }   # only in the repo: nothing to copy
  $si = Get-Item -LiteralPath $s
  if ($si.Length -eq 0) { Write-Host "SKIP (source is empty)        $n"; $empty++; continue }   # a truncated file must not replace a good one
  if (Test-Path -LiteralPath $d) {
    if ((Get-FileHash -LiteralPath $s).Hash -eq (Get-FileHash -LiteralPath $d).Hash) { $same++; continue }
    $di = Get-Item -LiteralPath $d
    if ($di.LastWriteTimeUtc -gt $si.LastWriteTimeUtc -and -not $Force) {
      Write-Host "SKIP (repo copy is newer)     $n   repo $($di.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))  work $($si.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))  (-Force overrides)"
      $newer++; continue
    }
  }
  if ($DryRun) { Write-Host "WOULD COPY                    $n" }
  else { Copy-Item -LiteralPath $s -Destination $d -Force; Write-Host "COPIED                        $n" }
  $copied++
}

# Scripts that exist only in the work folder are not copied; list them so a new module is not forgotten.
$only = @(Get-ChildItem -LiteralPath $Source -File -Filter '*.py' | Where-Object { $names -notcontains $_.Name } | ForEach-Object { $_.Name })
if ($only.Count) { Write-Host "NOTE not in the repo pipeline/ folder, so not copied: $($only -join ' ')" }

$verb = if ($DryRun) { 'would copy' } else { 'copied' }
Write-Host "$verb $copied, identical $same, newer in repo and skipped $newer, empty $empty. Source $Source -> $Destination"
if ($DryRun) { Write-Host 'Dry run: nothing was copied.' }
