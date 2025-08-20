<#
  setup.ps1 — create/update a local .venv (mamba/conda) and install deps
  Windows PowerShell equivalent of setup.sh
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Param(
  [string]$PythonVersion = $(if ($env:PY_VERSION) { $env:PY_VERSION } else { '3.11' })
)

$ScriptDir = $PSScriptRoot
Set-Location -Path $ScriptDir

$EnvPrefix = Join-Path $ScriptDir '.venv'

# Pick mamba/conda
if (Get-Command mamba -ErrorAction SilentlyContinue) {
  $CondaBin = 'mamba'
} elseif (Get-Command conda -ErrorAction SilentlyContinue) {
  $CondaBin = 'conda'
} else {
  Write-Error "ERROR: neither 'mamba' nor 'conda' found in PATH."
  exit 1
}

# Create env if missing
if (-not (Test-Path -Path $EnvPrefix)) {
  Write-Host ">> Creating env at $EnvPrefix (python=$PythonVersion)"
  & $CondaBin create -y -p $EnvPrefix "python=$PythonVersion"
} else {
  Write-Host ">> Env already exists at $EnvPrefix"
}

# Install requirements using conda run
$ReqPath = Join-Path $ScriptDir 'requirements.txt'
if (Test-Path -Path $ReqPath) {
  Write-Host ">> Installing requirements into $EnvPrefix"
  & $CondaBin run -p $EnvPrefix python -m pip install --upgrade pip
  & $CondaBin run -p $EnvPrefix python -m pip install -r $ReqPath
} else {
  Write-Warning "requirements.txt not found"
}

Write-Host ">> Setup complete."
Write-Host "To use this env:"
Write-Host "   $CondaBin run -p $EnvPrefix python -m streamlit run app.py"
Write-Host "or, if you prefer activation (requires conda init):"
Write-Host "   conda activate `"$EnvPrefix`""


