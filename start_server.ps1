# Inicia el servidor de la app en SEGUNDO PLANO (no se cae al cerrar la terminal).
# Uso:  .\start_server.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py  = Join-Path $env:USERPROFILE ".venvs\fatiga\Scripts\python.exe"
$log = Join-Path $env:TEMP "fatiga_server.log"
$err = Join-Path $env:TEMP "fatiga_server.err.log"

if (-not (Test-Path $py)) {
    Write-Host "No existe el entorno virtual. Ejecuta primero: .\run_local.ps1" -ForegroundColor Yellow
    exit 1
}

# Si ya esta corriendo, no lanzar otro.
$c = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($c) {
    Write-Host "El servidor YA esta corriendo (PID $($c.OwningProcess -join ','))." -ForegroundColor Green
} else {
    Start-Process -FilePath $py `
        -ArgumentList "-m","uvicorn","backend.main:app","--host","127.0.0.1","--port","8000" `
        -WorkingDirectory $PSScriptRoot -WindowStyle Hidden `
        -RedirectStandardOutput $log -RedirectStandardError $err

    Write-Host "Iniciando servidor..." -ForegroundColor Cyan
    $ok = $false
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 700
        try { Invoke-WebRequest "http://127.0.0.1:8000/api/health" -UseBasicParsing -TimeoutSec 4 | Out-Null; $ok = $true; break } catch {}
    }
    if ($ok) { Write-Host "Servidor activo." -ForegroundColor Green }
    else { Write-Host "No respondio. Revisa: $err" -ForegroundColor Red; exit 1 }
}

Start-Process "http://127.0.0.1:8000"
Write-Host "App disponible en http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Para detenerla: .\stop_server.ps1"
