# Run the FastAPI backend using the project venv (ensures pydantic>=2.10 and config loads .env).
# Usage: .\scripts\run_backend.ps1   or   .\scripts\run_backend.ps1 -Port 8002
param([int]$Port = 8002)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$venvPython = Join-Path $root ".venv" "Scripts" "python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating .venv and installing dependencies..."
    Set-Location $root
    python -m venv .venv
    & $venvPython -m pip install -q --upgrade pip
    & $venvPython -m pip install -q -r requirements.txt
}

Set-Location $root
& $venvPython -m uvicorn src.api.app:app --reload --port $Port
w