@echo off
title Flymetrics Command Center OS
echo ==================================================
echo   Iniciando Servidor Flymetrics OS...
echo ==================================================
set "SCRIPTS_DIR=%~dp0"
cd /d "%SCRIPTS_DIR%..\.."
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" backend\main.py
) else (
    python backend\main.py
)
pause

