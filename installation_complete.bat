@echo off
setlocal enabledelayedexpansion

echo ================================================
echo     Installation AnimeSamaCLI pour Windows
echo ================================================
echo.

echo Demande de privileges administrateur...
if not "%1"=="am_admin" (
    powershell -Command "Start-Process -Verb RunAs -FilePath '%0' -ArgumentList 'am_admin'"
    exit /b
)

where python >nul 2>&1
if %errorlevel% equ 0 (
    echo Python est deja installe.
    python --version
    set PYTHON_CMD=python
) else (
    echo Python n'est pas installe. Installation en cours...
    echo.
    echo Telechargement de Python 3.12...
    mkdir temp_install 2>nul
    cd temp_install
    
    curl -L -o python_installer.exe https://www.python.org/ftp/python/3.12.0/python-3.12.0-amd64.exe
    
    if exist "python_installer.exe" (
        echo Installation de Python 3.12 (cela peut prendre un moment)...
        python_installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0 Include_doc=0
        timeout /t 5 /nobreak > nul
        echo Python 3.12 installe!
    ) else (
        echo Impossible de telecharger Python. Veuillez l'installer manuellement.
        echo https://www.python.org/downloads/
        pause
        exit /b 1
    )
    
    cd ..
    rmdir /S /Q temp_install 2>nul
    set PYTHON_CMD=python
)

echo.
echo Installation des modules Python...
%PYTHON_CMD% -m pip install --upgrade pip
%PYTHON_CMD% -m pip install requests beautifulsoup4 windows-curses

echo.
echo ================================================
echo     Installation de MPV
echo ================================================
echo.

if exist "%ProgramFiles%\mpv\mpv.exe" (
    echo MPV est deja installe.
    set "MPV_PATH=%ProgramFiles%\mpv"
) else (
    echo Installation de MPV...
    
    mkdir mpv_install 2>nul
    cd mpv_install
    
    echo Telechargement de MPV...
    curl -L -o mpv.7z https://github.com/shinchiro/mpv-winbuild-cmake/releases/latest/download/mpv-x86_64-v3.7z
    
    if not exist "mpv.7z" (
        echo Tentative alternative de téléchargement...
        curl -L -o mpv.7z https://sourceforge.net/projects/mpv-player-windows/files/64bit/mpv-x86_64-20240414-git-1d52935.7z/download
    )
    
    if not exist "mpv.7z" (
        echo Impossible de telecharger MPV. 
        cd ..
        rmdir /S /Q mpv_install 2>nul
        goto SkipMPV
    )
    
    curl -L -o 7z.exe https://www.7-zip.org/a/7zr.exe
    
    if not exist "7z.exe" (
        echo Impossible de telecharger l'utilitaire d'extraction.
        cd ..
        rmdir /S /Q mpv_install 2>nul
        goto SkipMPV
    }
    
    echo Extraction de MPV...
    7z.exe x mpv.7z -y
    
    echo Installation de MPV...
    
    if not exist "%ProgramFiles%\mpv" mkdir "%ProgramFiles%\mpv" 2>nul
    if exist "%ProgramFiles%\mpv" (
        xcopy /E /Y mpv-* "%ProgramFiles%\mpv\"
        set "MPV_PATH=%ProgramFiles%\mpv"
    ) else (
        if not exist "%USERPROFILE%\mpv" mkdir "%USERPROFILE%\mpv" 2>nul
        xcopy /E /Y mpv-* "%USERPROFILE%\mpv\"
        set "MPV_PATH=%USERPROFILE%\mpv"
    )
    
    cd ..
    rmdir /S /Q mpv_install 2>nul
    
    echo Ajout de MPV au PATH...
    setx PATH "%PATH%;%MPV_PATH%" /M
)

echo.
echo Configuration de MPV...
echo # Configuration du lecteur multimedia > config.ini
echo default_player=1 >> config.ini

echo @echo off > "%USERPROFILE%\open_mpv.bat"
echo "%MPV_PATH%\mpv.exe" %%1 >> "%USERPROFILE%\open_mpv.bat"

:SkipMPV
echo.
echo ================================================
echo  Installation terminee!
echo.
echo  IMPORTANT: 
echo  - Redemarrez votre invite de commande pour 
echo    que les changements prennent effet
echo  - Si les videos ne s'ouvrent pas dans MPV, 
echo    utilisez: %USERPROFILE%\open_mpv.bat [URL]
echo.
echo  Pour lancer AnimeSamaCLI:
echo  python anime-sama.py
echo ================================================

pause 