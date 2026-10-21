# Detiene SOLO el servidor de Fatiga.
# No usa el puerto 8000: ese puerto puede ser de otro proyecto (Kandy).
# Uso:  .\stop_server.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$pidFile = Join-Path $PSScriptRoot ".server.pid"
$stopped = @()

function Stop-FatigaProcess([int]$id) {
    $p = Get-CimInstance Win32_Process -Filter "ProcessId = $id" -ErrorAction SilentlyContinue
    if ($p -and $p.CommandLine -match "backend\.main:app") {
        Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
        return $true
    }
    return $false
}

if (Test-Path $pidFile) {
    $savedPid = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($savedPid -and (Stop-FatigaProcess ([int]$savedPid))) {
        $stopped += $savedPid
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

# Respaldo: buscar procesos de esta app (backend.main:app) en el venv de Fatiga.
$procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -match "backend\.main:app" -and
    ($_.ExecutablePath -like "*\.venvs\fatiga\*" -or $_.CommandLine -like "*\.venvs\fatiga\*")
}
foreach ($p in $procs) {
    if ($stopped -notcontains [string]$p.ProcessId) {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        $stopped += [string]$p.ProcessId
    }
}

if ($stopped.Count -gt 0) {
    Write-Host "Servidor de Fatiga detenido (PID $($stopped -join ', '))." -ForegroundColor Yellow
} else {
    Write-Host "No habia servidor de Fatiga corriendo." -ForegroundColor Cyan
}
