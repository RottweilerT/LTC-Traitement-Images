@echo off
cd /d "%~dp0"

echo ==========================================
echo    INSTALLATION (a faire une seule fois)
echo ==========================================
echo.
echo Installe Python 3.12 si besoin, cree un environnement dans
echo le dossier .venv et y installe numpy, Pillow, OpenCV et SciPy.
echo Python 3.14 n'est pas utilise : Windows y bloque SciPy.
echo.

rem --- 1. Python 3.12 : trouve, sinon installe automatiquement ---------------
call :trouver_python
if not defined PY312 (
    echo Python 3.12 n'est pas installe sur cet ordinateur.
    echo Installation automatique de Python 3.12 ^(quelques minutes^) ...
    echo.
    call :installer_python
    call :trouver_python
)
if not defined PY312 (
    echo.
    echo ERREUR : Python 3.12 n'a pas pu etre installe automatiquement.
    echo Installez-le a la main depuis https://www.python.org/downloads/
    echo ^(version 3.12, "Windows installer 64-bit"^). Dans la premiere fenetre,
    echo cochez "Add python.exe to PATH", puis relancez INSTALLER.bat.
    echo.
    pause
    exit /b 1
)
echo Python 3.12 utilise : %PY312%
echo.

rem Un environnement .venv existant peut etre casse si Python 3.12 a ete
rem reinstalle, repare ou mis a jour : il est alors recree automatiquement.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import sys" >nul 2>&1
    if errorlevel 1 (
        echo L'environnement .venv existant ne fonctionne plus : il est recree.
        rmdir /s /q ".venv"
        if exist ".venv" (
            echo ERREUR : impossible de supprimer l'ancien dossier .venv.
            echo Fermez les fenetres du programme, supprimez .venv a la main, puis relancez.
            pause
            exit /b 1
        )
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo Creation de l'environnement .venv ...
    %PY312% -m venv .venv
    if errorlevel 1 (
        echo ERREUR : impossible de creer l'environnement .venv
        pause
        exit /b 1
    )
)

echo Installation des dependances ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERREUR : l'installation des dependances a echoue ^(voir ci-dessus^).
    pause
    exit /b 1
)

echo.
echo Verification :
".venv\Scripts\python.exe" -c "import numpy, scipy, cv2, PIL; print('Bibliotheques OK')"
if errorlevel 1 (
    echo ERREUR : une bibliotheque ne se charge pas ^(voir ci-dessus^).
    pause
    exit /b 1
)
".venv\Scripts\python.exe" run_pipeline.py --version

echo.
echo Creation du raccourci "LTC Traitement Images" sur le Bureau ...
set "PROJET=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$d=[Environment]::GetFolderPath('Desktop'); Remove-Item -LiteralPath (Join-Path $d 'Traitement de Timbres.lnk') -ErrorAction SilentlyContinue; $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'LTC Traitement Images.lnk')); $s.TargetPath=(Join-Path $env:PROJET 'LANCER_TRAITEMENT.bat'); $s.WorkingDirectory=$env:PROJET; $s.IconLocation=(Join-Path $env:PROJET 'ressources\icone.ico'); $s.Description='LTC Traitement Images'; $s.Save()"
if errorlevel 1 (
    echo Le raccourci n'a pas pu etre cree ^(sans consequence^) : lancez LANCER_TRAITEMENT.bat directement.
) else (
    echo Raccourci cree. Si vous deplacez ce dossier, relancez INSTALLER.bat pour le mettre a jour.
)

echo.
echo ==========================================
echo Installation terminee.
echo Lancez maintenant LANCER_TRAITEMENT.bat
echo ==========================================
echo.
pause
exit /b 0


rem ===========================================================================
rem Sous-programmes
rem ===========================================================================

:trouver_python
rem Cherche un Python 3.12 qui fonctionne. PY312 contient une commande prete a
rem l'emploi : "py -3.12", ou le chemin complet entre guillemets. Le chemin
rem n'est jamais relu depuis la sortie d'un programme : la console Windows y
rem abime les accents d'un nom de compte (ex. Stephanie avec un accent).
set "PY312="
py -3.12 -c "import sys" >nul 2>&1 && set "PY312=py -3.12"
if defined PY312 exit /b 0
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -c "import sys" >nul 2>&1 && set PY312="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if defined PY312 exit /b 0
if exist "%ProgramFiles%\Python312\python.exe" "%ProgramFiles%\Python312\python.exe" -c "import sys" >nul 2>&1 && set PY312="%ProgramFiles%\Python312\python.exe"
exit /b 0

:installer_python
rem 1) winget (Windows 10 et 11), pour l'utilisateur courant : pas besoin
rem    de droits administrateur.
where winget >nul 2>&1
if not errorlevel 1 (
    winget install --exact --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
    call :trouver_python
    if defined PY312 exit /b 0
)
rem 2) Sinon : installateur officiel de python.org, en mode silencieux,
rem    avec "Add python.exe to PATH" coche (PrependPath=1).
echo Telechargement de Python 3.12 depuis python.org ...
set "PYSETUP=%TEMP%\python-3.12.10-amd64.exe"
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = 'Tls12'; Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile $env:PYSETUP"
if errorlevel 1 (
    echo Le telechargement de Python a echoue ^(connexion internet ?^).
    exit /b 1
)
echo Installation de Python 3.12 ...
"%PYSETUP%" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_test=0
del "%PYSETUP%" >nul 2>&1
exit /b 0
