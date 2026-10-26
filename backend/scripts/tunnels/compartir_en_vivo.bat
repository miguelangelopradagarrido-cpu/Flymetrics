@echo off
title Compartir Flymetrics en Vivo (Auto-Sync)
echo ========================================================
echo   GENERANDO ENLACE PUBLICO SEGURO PARA FLYMETRICS
echo ========================================================
echo.
echo Iniciando tunel seguro hacia tu servidor local (Puerto 3000)...
echo En breves segundos veras tu enlace https://....trycloudflare.com
echo.
if exist "%~dp0cloudflared.exe" (
    "%~dp0cloudflared.exe" tunnel --url http://127.0.0.1:3000
) else (
    npx --yes cloudflared tunnel --url http://localhost:3000
)
pause
