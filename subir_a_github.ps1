# Script PowerShell para subir cambios a GitHub en Flymetrics
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Write-Host ""
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "           FLYMETRICS - ASISTENTE DE SUBIDA A GITHUB          " -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/4] Verificando cambios en el proyecto..." -ForegroundColor Yellow
git status -s
Write-Host ""

Write-Host "[2/4] Agregando todos los archivos modificados y multimedia..." -ForegroundColor Yellow
git add -A
Write-Host ""

$commitMsg = Read-Host "Ingresa una descripcion del cambio (o presiona ENTER para auto)"
if ([string]::IsNullOrWhiteSpace($commitMsg)) {
    $now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $commitMsg = "Actualizacion automatica Flymetrics - $now"
}

Write-Host ""
Write-Host "[3/4] Creando commit: '$commitMsg'..." -ForegroundColor Yellow
git commit -m $commitMsg
Write-Host ""

Write-Host "[4/4] Subiendo a la rama principal (origin/main)..." -ForegroundColor Yellow
git push origin main
Write-Host ""

if ($LASTEXITCODE -eq 0) {
    Write-Host "=====================================================================" -ForegroundColor Green
    Write-Host "   ✅ ¡TODO EL TRABAJO SE HA SUBIDO EXITOSAMENTE A GITHUB! ✅" -ForegroundColor Green
    Write-Host "   Hostless desplegara la aplicacion en vivo de forma automatica." -ForegroundColor Green
    Write-Host "=====================================================================" -ForegroundColor Green
}
else {
    Write-Host "=====================================================================" -ForegroundColor Red
    Write-Host "   ❌ Ocurrio un problema al subir a GitHub. Revisa la conexion." -ForegroundColor Red
    Write-Host "=====================================================================" -ForegroundColor Red
}

Write-Host ""
Read-Host "Presiona ENTER para salir"
