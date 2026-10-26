@echo off
title Flymetrics - Tunel Cloudflare Seguro
cls
echo ================================================================
echo      FLYMETRICS - TUNEL CLOUDFLARE PUBLICO (100%% GRATUITO)
echo ================================================================
echo.
echo  Iniciando conexion hacia tu servidor local http://127.0.0.1:3000...
echo.

"%~dp0..\..\..\.venv\Scripts\python.exe" "%~dp0run_tunel_gratis.py"

pause
