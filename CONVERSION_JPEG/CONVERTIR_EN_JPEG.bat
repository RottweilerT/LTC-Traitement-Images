@echo off
title LTC Traitement Images - conversion JPEG
rem Le programme se trouve dans le dossier parent.
cd /d "%~dp0.."

echo ==========================================
echo        CONVERSION TIFF EN JPEG
echo ==========================================
echo.
echo Dossier source      : CONVERSION_JPEG\TIF_A_CONVERTIR
echo Dossier destination : CONVERSION_JPEG\JPEG_CONVERTIS
echo.

rem Choix de Python : environnement du projet (.venv), sinon Python 3.12, sinon python.
set "PY="
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import numpy, PIL" >nul 2>&1
    if not errorlevel 1 set "PY=.venv\Scripts\python.exe"
)
if not defined PY (
    py -3.12 -c "import numpy, PIL" >nul 2>&1
    if not errorlevel 1 set "PY=py -3.12"
)
if not defined PY set "PY=python"

%PY% -m image_pipeline.jpeg_conversion "CONVERSION_JPEG\TIF_A_CONVERTIR" "CONVERSION_JPEG\JPEG_CONVERTIS" %*
if errorlevel 1 (
    echo.
    echo ==========================================
    echo Une erreur est survenue ^(voir ci-dessus^).
    echo Si le message parle d'un module introuvable,
    echo double-cliquez une fois sur INSTALLER.bat
    echo ^(dans le dossier du logiciel^) puis relancez.
    echo ==========================================
) else (
    echo.
    echo ==========================================
    echo Conversion terminee. JPEG dans JPEG_CONVERTIS.
    echo ==========================================
)

echo.
echo Vous pouvez fermer cette fenetre.
echo.
pause
