# Levanta la aplicacion en local (Windows PowerShell)
# Uso:  .\run_local.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$venv = Join-Path $env:USERPROFILE ".venvs\fatiga"

if (-not (Test-Path $venv)) {
    Write-Host "Creando entorno virtual en $venv ..."
    python -m venv $venv
}

Write-Host "Instalando dependencias ..."
& "$venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
& "$venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt

Write-Host ""
Write-Host "Abriendo la aplicacion en http://127.0.0.1:8010"
Write-Host "(Ctrl+C para detener)"
Write-Host ""

& "$venv\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8010 --reload
