# Detiene el servidor de la app (el que escucha en el puerto 8000).
# Uso:  .\stop_server.ps1
$c = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($c) {
    $c.OwningProcess | Select-Object -Unique | ForEach-Object {
        Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
    }
    Write-Host "Servidor detenido." -ForegroundColor Yellow
} else {
    Write-Host "No habia servidor corriendo en el puerto 8000." -ForegroundColor Cyan
}
