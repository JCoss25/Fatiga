@echo off
REM Primera vez / desarrollo: crea el entorno, instala dependencias y abre la app.
REM Manten esta ventana abierta mientras uses la app (Ctrl+C para detener).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_local.ps1"
pause
