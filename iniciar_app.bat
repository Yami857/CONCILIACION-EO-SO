@echo off
chcp 65001 >nul
title Conciliador EO / SO

rem Se ubica siempre en la carpeta del .bat, sin depender del directorio actual.
cd /d "%~dp0"

echo Iniciando el Conciliador EO / SO...
echo Se abrira el navegador en http://127.0.0.1:5000
echo Para detener la aplicacion presione Ctrl+C en esta ventana.
echo.

rem Abre el navegador tras una espera breve, mientras el servidor arranca.
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 4; Start-Process 'http://127.0.0.1:5000'"

uv run python wsgi.py

echo.
echo La aplicacion se ha detenido.
pause
