<#
  px.ps1 — ensure env is ready, then run px.py in it (passes args through)
  Windows PowerShell equivalent of px.sh
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ScriptDir = $PSScriptRoot
Set-Location -Path $ScriptDir

Param(
  [switch]$Reset,
  [switch]$Restart,
  [switch]$Help,
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Passthru
)

if ($Help) {
  @'
Usage: .\px.ps1 [-Help] [-Reset] [-Restart] [-- <px.py args>]

Wrapper options (handled by px.ps1):
  -Help      Show this help and exit
  -Reset     Clean data load only:
             - Clears cached data (./data/)
             - Clears debug snapshots (./debug/)
  -Restart   Rebuild environment from scratch (also implies setup):
             - Removes ./.venv and recreates it via setup.ps1

Notes:
  - Arguments after "--" are passed directly to px.py.
  - To see px.py's own CLI help, run:  .\px.ps1 -- --help
  - This wrapper ensures the conda/mamba env at ./.venv exists and then runs:
      python px.py <args>
'@ | Write-Host
  exit 0
}

$EnvPrefix = Join-Path $ScriptDir '.venv'

if ($Restart -and (Test-Path $EnvPrefix)) {
  Write-Host ">> Removing existing env: $EnvPrefix"
  Remove-Item -Recurse -Force $EnvPrefix
}

if ($Reset) {
  Write-Host ">> Resetting cached data and debug snapshots"
  New-Item -ItemType Directory -Force -Path (Join-Path $ScriptDir 'data') | Out-Null
  New-Item -ItemType Directory -Force -Path (Join-Path $ScriptDir 'debug') | Out-Null
  Get-ChildItem -Path (Join-Path $ScriptDir 'data') -Filter '*.parquet' -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
  if (Test-Path (Join-Path $ScriptDir 'debug')) { Remove-Item -Recurse -Force (Join-Path $ScriptDir 'debug' '*') -ErrorAction SilentlyContinue }
}

if (-not (Test-Path $EnvPrefix)) {
  & (Join-Path $ScriptDir 'setup.ps1')
}

# pick mamba or conda
if (Get-Command mamba -ErrorAction SilentlyContinue) {
  $CondaBin = 'mamba'
} elseif (Get-Command conda -ErrorAction SilentlyContinue) {
  $CondaBin = 'conda'
} else {
  Write-Error "ERROR: neither 'mamba' nor 'conda' found in PATH."
  exit 1
}

& $CondaBin run -p $EnvPrefix python px.py @Passthru


