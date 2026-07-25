@echo off
setlocal enabledelayedexpansion

echo ================================================
echo     AnimeSamaCLI Setup (User Mode, No Admin)
echo ================================================
echo.

set "INSTALL_DIR=%USERPROFILE%\AnimeSamaCLI"
set "DB_DIR=%USERPROFILE%\.local\share\animesama-cli"

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "%DB_DIR%" mkdir "%DB_DIR%"

where python >nul 2>&1
if %errorlevel% equ 0 (
    echo Python detecte :
    python --version
) else (
    echo Python n'est pas installe. Installez Python 3.12+ puis relancez ce script :
    echo https://www.python.org/downloads/
    exit /b 1
)

echo.
echo ================================================
echo     Installation de animesama-cli via pipx
echo ================================================
echo.

python -m pip install --upgrade pip
python -m pip install --user pipx
python -m pipx ensurepath
python -m pipx install --force animesama-cli

echo.
echo ================================================
echo     Installation de MPV
echo ================================================
echo.

if exist "%INSTALL_DIR%\mpv\mpv.exe" (
    echo MPV est deja installe.
) else (
    echo Telechargement de MPV...
    cd "%INSTALL_DIR%"
    curl -L -A "Mozilla/5.0" -o mpv.zip https://nightly.link/mpv-player/mpv/workflows/build/master/mpv-x86_64-pc-windows-msvc.zip

    if not exist "mpv.zip" (
        echo Echec du telechargement de MPV. Lien manuel :
        echo https://nightly.link/mpv-player/mpv/workflows/build/master/mpv-x86_64-pc-windows-msvc.zip
        cd "%~dp0"
        goto SkipMPV
    )

    echo Extraction de MPV...
    powershell -Command "Expand-Archive -Path 'mpv.zip' -DestinationPath '.' -Force"

    set "MPV_EXTRACTED="
    for /d %%D in (mpv-*) do set "MPV_EXTRACTED=%%D"

    if not exist "%INSTALL_DIR%\mpv" mkdir "%INSTALL_DIR%\mpv"
    if not "!MPV_EXTRACTED!"=="" (
        xcopy "!MPV_EXTRACTED!\*" "%INSTALL_DIR%\mpv\" /E /Y /Q
        rmdir /s /q "!MPV_EXTRACTED!"
        del /q mpv.zip
        echo MPV installe dans %INSTALL_DIR%\mpv
    ) else (
        echo Echec de l'extraction de MPV.
    )
    cd "%~dp0"
)
:SkipMPV

echo.
echo ================================================
echo     Ajout de MPV au PATH
echo ================================================
echo.

for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "OLD_PATH=%%B"
set "NEW_PATH=!OLD_PATH!"
if not "!NEW_PATH!"=="" (
    echo !NEW_PATH! | findstr /C:"%INSTALL_DIR%\mpv" >nul
    if errorlevel 1 set "NEW_PATH=!NEW_PATH!;%INSTALL_DIR%\mpv"
) else (
    set "NEW_PATH=%INSTALL_DIR%\mpv"
)
setx PATH "!NEW_PATH!"

echo.
echo ================================================
echo  Installation terminee !
echo.
echo  FERMEZ et rouvrez votre terminal, puis lancez :
echo      animesama-cli
echo.
echo  Si la commande n'est pas trouvee, verifiez que ces
echo  dossiers sont dans votre PATH utilisateur :
echo      %USERPROFILE%\.local\bin
echo      %INSTALL_DIR%\mpv
echo ================================================
