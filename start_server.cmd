@echo off
REM Inicia la app en segundo plano y abre el navegador.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_server.ps1"
