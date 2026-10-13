@echo off
REM Detiene la app.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_server.ps1"
pause
