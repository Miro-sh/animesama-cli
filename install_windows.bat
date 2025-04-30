@echo off
setlocal enabledelayedexpansion

echo ================================================
echo     AnimeSamaCLI Setup (User Mode, No Admin)
echo ================================================
echo.

:: Set up paths
set "INSTALL_DIR=%USERPROFILE%\AnimeSamaCLI"
set "SCRIPT_DIR=%INSTALL_DIR%\scripts"

echo Setting up installation directories...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "%SCRIPT_DIR%" mkdir "%SCRIPT_DIR%"

:: Check for Python
where python >nul 2>&1
if %errorlevel% equ 0 (
    echo Python is already installed.
    python --version
    set PYTHON_CMD=python
) else (
    echo Python is not installed. Please install Python 3.12+ and relancez ce script.
    echo https://www.python.org/downloads/
    exit /b 1
)

echo.
echo Installing Python modules...
%PYTHON_CMD% -m pip install --upgrade pip
%PYTHON_CMD% -m pip install requests beautifulsoup4 windows-curses

echo.
echo ================================================
echo     MPV Installation
echo ================================================
echo.

if exist "%INSTALL_DIR%\mpv\mpv.exe" (
    echo MPV is already installed.
    set "MPV_PATH=%INSTALL_DIR%\mpv"
) else (
    echo Installing MPV locally...
    
    REM Création des répertoires nécessaires
    set "MPV_DIR=%INSTALL_DIR%\mpv"
    
    REM S'assurer que le dossier principal AnimeSamaCLI existe
    if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
    
    REM Téléchargement directement dans le dossier AnimeSamaCLI principal
    cd "%INSTALL_DIR%"
    echo Téléchargement de MPV dans %INSTALL_DIR%...
    curl -L -A "Mozilla/5.0" -o mpv.zip https://nightly.link/mpv-player/mpv/workflows/build/master/mpv-x86_64-pc-windows-msvc.zip
    
    if not exist "mpv.zip" (
        echo Echec du téléchargement de MPV. Essayez ce lien manuellement :
        echo https://nightly.link/mpv-player/mpv/workflows/build/master/mpv-x86_64-pc-windows-msvc.zip
        cd "%~dp0"
        goto EndMPV
    )
    
    REM Extraction du zip MPV directement dans le dossier AnimeSamaCLI
    echo Extraction de MPV dans %INSTALL_DIR%...
    powershell -Command "Expand-Archive -Path 'mpv.zip' -DestinationPath '.' -Force"
    
    REM Trouve le dossier extrait (il commence par mpv-)
    set "MPV_EXTRACTED="
    for /d %%D in (mpv-*) do (
        set "MPV_EXTRACTED=%%D"
    )
    
    REM Création du dossier mpv s'il n'existe pas
    if not exist "%MPV_DIR%" mkdir "%MPV_DIR%"
    
    REM Utilise delayed expansion pour copier le contenu
    if not "!MPV_EXTRACTED!"=="" (
        echo Copie des fichiers de !MPV_EXTRACTED! vers %MPV_DIR%...
        xcopy "!MPV_EXTRACTED!\*" "%MPV_DIR%\" /E /Y /Q
        echo MPV installé avec succès dans %MPV_DIR% !
        
        REM Nettoyage: suppression du dossier extrait et du zip
        rmdir /s /q "!MPV_EXTRACTED!"
        del /q mpv.zip
    ) else (
        echo Echec de l'extraction de MPV. Extraction manuelle requise.
    )
    
    REM Retour au répertoire initial
    cd "%~dp0"
    :EndMPV
    set "MPV_PATH=%INSTALL_DIR%\mpv"
)

echo.
echo ================================================
echo     AnimeSamaCLI Installation
echo ================================================
echo.

echo Downloading AnimeSamaCLI...
curl -L -o "%SCRIPT_DIR%\anime-sama.py" https://raw.githubusercontent.com/DictateurMiro/animesama-cli/master/anime-sama.py

echo Creating launcher script...
(
echo @echo off
echo python "%SCRIPT_DIR%\anime-sama.py" %%*
) > "%INSTALL_DIR%\animesama-cli.bat"

echo.
echo ================================================
echo     Création des raccourcis exécutables
echo ================================================
echo.

REM Création des fichiers batch partout où c'est nécessaire
echo Création des scripts de lancement pour chaque emplacement possible...

REM 1. Dans le dossier utilisateur principal
echo @echo off > "%USERPROFILE%\mpv.bat"
echo "%INSTALL_DIR%\mpv\mpv.exe" %%* >> "%USERPROFILE%\mpv.bat"
copy "%INSTALL_DIR%\animesama-cli.bat" "%USERPROFILE%\animesama-cli.bat" /Y
echo Raccourcis créés dans %USERPROFILE%

REM 2. Dans le dossier Windows
echo Tentative de création de raccourcis dans le dossier Windows...
echo @echo off > "%WINDIR%\mpv.bat"
echo "%INSTALL_DIR%\mpv\mpv.exe" %%* >> "%WINDIR%\mpv.bat"
copy "%INSTALL_DIR%\animesama-cli.bat" "%WINDIR%\animesama-cli.bat" /Y 2>nul
if %errorlevel% equ 0 (
    echo Raccourcis créés dans %WINDIR%
) else (
    echo Impossible d'écrire dans %WINDIR% (droits d'admin requis)
)

echo.
echo ================================================
echo     Mise à jour du PATH
echo ================================================
echo.

echo Modification directe du PATH utilisateur...

REM Obtenir le PATH actuel
for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "OLD_PATH=%%B"

REM Nettoyer le PATH des entrées erronnées
set "CLEAN_PATH=!OLD_PATH!"
echo PATH original: !OLD_PATH!

REM Préparer un PATH propre
echo Nettoyage du PATH...
set "CLEAN_PATH=%CLEAN_PATH:Files\mpv;=%"
set "CLEAN_PATH=%CLEAN_PATH:mpv\Files;=%"

REM Ajout des chemins corrects s'ils ne sont pas déjà présents
set "NEED_MPV=1"
set "NEED_CLI=1"

echo PATH nettoyé: !CLEAN_PATH!

if not "!CLEAN_PATH!"=="" (
    echo !CLEAN_PATH! | findstr /C:"%INSTALL_DIR%\mpv" >nul && set "NEED_MPV=0"
    echo !CLEAN_PATH! | findstr /C:"%INSTALL_DIR%" >nul && set "NEED_CLI=0"
)

set "NEW_PATH=!CLEAN_PATH!"

if "!NEED_MPV!"=="1" (
    if "!NEW_PATH!"=="" (
        set "NEW_PATH=%INSTALL_DIR%\mpv"
    ) else (
        set "NEW_PATH=!NEW_PATH!;%INSTALL_DIR%\mpv"
    )
)

if "!NEED_CLI!"=="1" (
    if "!NEW_PATH!"=="" (
        set "NEW_PATH=%INSTALL_DIR%"
    ) else (
        set "NEW_PATH=!NEW_PATH!;%INSTALL_DIR%"
    )
)

echo Mise à jour du PATH: !NEW_PATH!
setx PATH "!NEW_PATH!"

echo.
echo ================================================
echo  Installation complete!
echo.
echo  IMPORTANT: 
echo  - Les raccourcis .bat ont été créés à plusieurs endroits pour maximiser les chances de fonctionnement
echo  - Pour utiliser les commandes, FERMEZ COMPLÈTEMENT votre terminal et ouvrez-en un nouveau
echo  - Vous pouvez utiliser les commandes:
echo      animesama-cli
echo      mpv
echo.
echo  Si les commandes ne marchent toujours pas:
echo  1. Utilisez le chemin complet:
echo     "%INSTALL_DIR%\mpv\mpv.exe"
echo     "%INSTALL_DIR%\animesama-cli.bat"
echo  2. Utilisez les .bat créés dans votre dossier utilisateur:
echo     "%USERPROFILE%\mpv.bat"
echo     "%USERPROFILE%\animesama-cli.bat"
echo  3. Ajoutez manuellement ces dossiers à votre PATH:
echo     %INSTALL_DIR%
echo     %INSTALL_DIR%\mpv
echo ================================================

REM Suppression du fichier d'installation
echo Suppression du fichier d'installation...
(goto) 2>nul & del "%~f0"

:: 35YUZ3EHFHZE