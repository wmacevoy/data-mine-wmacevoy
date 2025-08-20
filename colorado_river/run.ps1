<#
  run.ps1 — ensure env is ready, then run Streamlit in it
  Windows PowerShell equivalent of run.sh
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ScriptDir = $PSScriptRoot
Set-Location -Path $ScriptDir

# Args
Param(
  [switch]$Debug,
  [switch]$Reset,
  [switch]$Restart,
  [switch]$Help
)

if ($Help) {
  @'
Usage: .\run.ps1 [-Help] [-Debug] [-Reset] [-Restart]

Options:
  -Help      Show this help and exit
  -Debug     Enable extra debugging (implies -Reset):
             - Clears cached data (./data/)
             - Clears debug snapshots (./debug/)
             - Sets STREAMLIT_DEBUG_SNAPSHOTS=1
  -Reset     Clean data load only:
             - Clears cached data (./data/)
             - Clears debug snapshots (./debug/)
  -Restart   Rebuild environment from scratch (also implies setup):
             - Removes ./.venv and recreates it via setup.ps1

Behavior:
  - The script auto-creates .streamlit/config.toml to suppress first-run prompts
  - Streamlit runs headless using python -m streamlit
'@ | Write-Host
  exit 0
}

if ($Debug) { $Reset = $true }

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

# Ensure .streamlit config
$StreamlitDir = Join-Path $ScriptDir '.streamlit'
New-Item -ItemType Directory -Force -Path $StreamlitDir | Out-Null
$ConfigPath = Join-Path $StreamlitDir 'config.toml'
if (-not (Test-Path $ConfigPath)) {
  @"
[browser]
gatherUsageStats = false

[server]
headless = true
"@ | Set-Content -NoNewline -Path $ConfigPath
}

$env:STREAMLIT_BROWSER_GATHERUSAGESTATS = 'false'
$env:STREAMLIT_SERVER_HEADLESS = 'true'
if ($Debug) { $env:STREAMLIT_DEBUG_SNAPSHOTS = '1' }

# pick mamba or conda
if (Get-Command mamba -ErrorAction SilentlyContinue) {
  $CondaBin = 'mamba'
} elseif (Get-Command conda -ErrorAction SilentlyContinue) {
  $CondaBin = 'conda'
} else {
  Write-Error "ERROR: neither 'mamba' nor 'conda' found in PATH."
  exit 1
}

& $CondaBin run -p $EnvPrefix python -m streamlit run app.py


