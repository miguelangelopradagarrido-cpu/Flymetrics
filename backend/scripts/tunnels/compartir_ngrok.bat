@echo off
title Compartir Flymetrics con ngrok (Puerto 3000)
echo ========================================================
echo   COMPARTIR FLYMETRICS CON NGROK EN VIVO
echo ========================================================
echo.
echo Conectando tu servidor local (http://localhost:3000) a internet...
echo.
ngrok http 3000
pause
