@echo off
chcp 65001 >nul
title Flymetrics - Subir Trabajo a GitHub
color 0B
echo.
echo =====================================================================
echo            FLYMETRICS - ASISTENTE DE SUBIDA A GITHUB 
echo =====================================================================
echo.
echo [1/4] Verificando cambios en el proyecto...
git status -s
echo.
echo [2/4] Agregando todos los archivos modificados y multimedia...
git add -A
echo.
set /p USER_MSG="Ingresa una descripcion del cambio (o presiona ENTER para auto): "
if "%USER_MSG%"=="" (
    set USER_MSG=Actualizacion automatica Flymetrics - %date% %time%
)
echo.
echo [3/4] Creando commit: "%USER_MSG%"
git commit -m "%USER_MSG%"
echo.
echo [4/4] Subiendo a la rama principal (origin/main)...
git push origin main
echo.
if %ERRORLEVEL% equ 0 (
    color 0A
    echo =====================================================================
    echo    ✅ ¡TODO EL TRABAJO SE HA SUBIDO EXITOSAMENTE A GITHUB! ✅
    echo    Hostless actualizara la aplicacion en vivo automaticamente.
    echo =====================================================================
) else (
    color 0C
    echo =====================================================================
    echo    ❌ Ocurrio un problema al subir a GitHub. Revisa la conexion.
    echo =====================================================================
)
echo.
pause
