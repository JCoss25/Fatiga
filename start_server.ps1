# Inicia la app de Fatiga en SEGUNDO PLANO.
# Puerto propio (8010): no toca el 8000, que puede estar ocupado por otro proyecto.
# Uso:  .\start_server.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$Port = 8010
$py = Join-Path $env:USERPROFILE ".venvs\fatiga\Scripts\python.exe"
$log = Join-Path $env:TEMP "fatiga_server.log"
$err = Join-Path $env:TEMP "fatiga_server.err.log"
$pidFile = Join-Path $PSScriptRoot ".server.pid"
$base = "http://127.0.0.1:$Port"

function Test-Fatiga {
    try {
        $r = Invoke-RestMethod "$base/api/ping" -TimeoutSec 2
        return ($r.app -eq "fatiga")
    } catch {
        return $false
    }
}

if (-not (Test-Path $py)) {
    Write-Host "No existe el entorno virtual. Ejecuta primero: .\run_local.ps1" -ForegroundColor Yellow
    exit 1
}

# Si ya hay una instancia registrada y viva, no lanzar otra.
if (Test-Path $pidFile) {
    $oldPid = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($oldPid) {
        $old = Get-CimInstance Win32_Process -Filter "ProcessId = $oldPid" -ErrorAction SilentlyContinue
        if ($old -and $old.CommandLine -match "backend\.main:app") {
            Write-Host "El servidor YA esta corriendo (PID $oldPid)." -ForegroundColor Green
            Start-Process $base
            exit 0
        }
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

# Si el puerto esta tomado, distinguir si es Fatiga o es otro proyecto.
$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    if (Test-Fatiga) {
        Write-Host "Fatiga ya responde en $base (PID $($listener.OwningProcess -join ','))." -ForegroundColor Green
        Start-Process $base
        exit 0
    }
    $owner = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)" -ErrorAction SilentlyContinue
    Write-Host "El puerto $Port esta ocupado por otro proceso (PID $($listener.OwningProcess)):" -ForegroundColor Red
    Write-Host "  $($owner.CommandLine)" -ForegroundColor DarkGray
    Write-Host "No se inicio Fatiga para no interferir. Libera el puerto o cambia `$Port en este script." -ForegroundColor Red
    exit 1
}

Write-Host "Iniciando servidor en $base ..." -ForegroundColor Cyan

$proc = Start-Process -FilePath $py `
    -ArgumentList "-m","uvicorn","backend.main:app","--host","127.0.0.1","--port",$Port `
    -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $log -RedirectStandardError $err

Set-Content -Path $pidFile -Value $proc.Id -Encoding ASCII

$ok = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 700
    if (Test-Fatiga) { $ok = $true; break }
}

if ($ok) {
    Write-Host "Servidor activo. PID $($proc.Id)" -ForegroundColor Green
    Write-Host "App:      $base" -ForegroundColor Green
    Write-Host "Kiosco:   $base/kiosco.html" -ForegroundColor Green
    Write-Host "Panel:    $base/panel.html" -ForegroundColor Green
    Write-Host "API docs: $base/docs" -ForegroundColor Green
} else {
    Write-Host "No respondio. Revisa: $err" -ForegroundColor Red
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    exit 1
}

Start-Process $base
Write-Host "Para detenerla: .\stop_server.ps1" -ForegroundColor DarkGray
