@echo off
title Flymetrics Server + Tunel Cloudflare Gratis
echo ==================================================
echo   Iniciando Flymetrics OS + Tunel Gratis (HTTPS)
echo ==================================================

set "SCRIPTS_DIR=%~dp0"
cd /d "%SCRIPTS_DIR%..\.."

echo [1/2] Levantando Servidor Backend en puerto 3000...
if exist ".venv\Scripts\python.exe" (
    start "Flymetrics API Server" cmd /k "cd /d "%SCRIPTS_DIR%..\.." && .venv\Scripts\python.exe backend\main.py"
) else (
    start "Flymetrics API Server" cmd /k "cd /d "%SCRIPTS_DIR%..\.." && python backend\main.py"
)

timeout /t 3 /nobreak >nul

echo [2/2] Levantando Tunel Cloudflare Publico Gratuito...
if exist "%SCRIPTS_DIR%tunnels\cloudflared.exe" (
    if exist ".venv\Scripts\python.exe" (
        start "Flymetrics Tunel HTTPS" cmd /k "cd /d "%SCRIPTS_DIR%tunnels" && "%SCRIPTS_DIR%..\..\.venv\Scripts\python.exe" run_tunel_gratis.py"
    ) else (
        start "Flymetrics Tunel HTTPS" cmd /k "cd /d "%SCRIPTS_DIR%tunnels" && python run_tunel_gratis.py"
    )
) else (
    echo [!] No se encontro cloudflared.exe en backend\scripts\tunnels
)

echo.
echo ==================================================
echo  Listo! Servidor y Tunel ejecutandose en vivo.
echo  Tu URL publica aparecera en la ventana del Tunel.
echo ==================================================
pause
