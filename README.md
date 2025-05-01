<p align=center>
<br>
<a href="#Linux"><img src="https://img.shields.io/badge/os-linux-90ee90">
<a href="#Windows"><img src="https://img.shields.io/badge/os-windows-90ee90">
<br>
<h1 align="center">
<a href="https://discord.gg/MwHAXPpJ8C"><img src="https://invidget.switchblade.xyz/MwHAXPpJ8C?language=en"></a>
<br>
<a href="https://github.com/DictateurMiro"><img src="https://img.shields.io/badge/owner-DictateurMiro-ff6344"></a>
</p>

<h3 align="center">
A CLI to browse and watch anime from <a href="https://anime-sama.fr">anime-sama.fr</a> (in French dub and with subtitles).
</h3>

<h1 align="center">
	Showcase
</h1>

[showcase.webm](https://user-images.githubusercontent.com/44473782/224679247-0856e652-f187-4865-bbcf-5a8e5cf830da.webm)

## Table of Contents

- [Install](#install)
  - [Linux](#first-install)
  - [Windows](#second-install)
- [Uninstall](#uninstall)
- [Dependencies](#dependencies)
- [FAQ](#faq)
  - [Another Language](#another-language)
- [Contribution Guidelines](./contribution.md)
- [Disclaimer](./disclaimer.md)

## Install

[![Packaging status](https://repology.org/badge/vertical-allrepos/animesama-cli.svg?minversion=1.0.0)](https://repology.org/project/animesama-cli/versions)

### First Install

*These Platforms have rock solid support and are used by maintainers and large parts of the userbase.*

<details><summary><b>Linux</b></summary>



*Make sure you have all the necessary dependencies installed. For Debian-based distributions, you'll need curl, python3, and mpv. The installation script will handle the rest of the setup process.*

<details><summary>Debian</summary>

```sh
sudo apt-get install curl -y
curl -fsSL https://raw.githubusercontent.com/DictateurMiro/animesama-cli/master/install.sh -o /tmp/animesama-install.sh && chmod +x /tmp/animesama-install.sh && sh /tmp/animesama-install.sh
```
</details>

<details><summary>Arch</summary>

```sh
yay -S animesama-cli
```
</details></details>

### Second Install

<details><summary><b>Windows</b></summary>

Open powershell (don't need admin perm) and paste the command below
```powershell
irm "https://raw.githubusercontent.com/DictateurMiro/animesama-cli/refs/heads/master/setup_animesama_cli.bat" -OutFile install.bat; .\install.bat
```

</details>

## Uninstall

<details>

* AUR:
```sh
yay -R animesama-cli
```

* Linux:
```sh
sudo rm /usr/local/bin/animesama-cli
rm -rf ~/animesama-cli
rm -rf ~/.local/share/animesama-venv
```

* Windows:
```sh
@echo off
set "INSTALL_DIR=%USERPROFILE%\AnimeSamaCLI"

if exist "%USERPROFILE%\mpv.bat" del /q "%USERPROFILE%\mpv.bat"
if exist "%USERPROFILE%\animesama-cli.bat" del /q "%USERPROFILE%\animesama-cli.bat"
if exist "%WINDIR%\mpv.bat" del /q "%WINDIR%\mpv.bat" 2>nul
if exist "%WINDIR%\animesama-cli.bat" del /q "%WINDIR%\animesama-cli.bat" 2>nul

rd /s /q "%INSTALL_DIR%" 2>nul

for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "OLD_PATH=%%B"
setlocal enabledelayedexpansion
set "NEW_PATH=!OLD_PATH!"
set "NEW_PATH=!NEW_PATH:;%INSTALL_DIR%\mpv=!"
set "NEW_PATH=!NEW_PATH:;%INSTALL_DIR%=!"
set "NEW_PATH=!NEW_PATH:%INSTALL_DIR%\mpv;=!"
set "NEW_PATH=!NEW_PATH:%INSTALL_DIR%;=!"
set "NEW_PATH=!NEW_PATH:%INSTALL_DIR%\mpv=!"
set "NEW_PATH=!NEW_PATH:%INSTALL_DIR%=!"
setx PATH "!NEW_PATH!"
endlocal
```

</details>

## Dependencies

### Python Dependencies
- requests: HTTP library for making web requests
- beautifulsoup4 (bs4): HTML/XML parser for web scraping
- sqlite3: Built-in module for SQLite database operations
- curses: Terminal-based user interface library
- windows-curses: Windows version of curses
- re: Built-in module for regular expression operations
- json: Built-in module for JSON parsing/generation
- sys: Built-in module for interpreter interaction
- os: Built-in module for OS-related functionality
- time: Built-in module for time functions
- datetime: Built-in module for date/time manipulation
- locale: Built-in module for localization support
- pathlib: Built-in module for filesystem path operations

### System Dependencies
- mpv: Media player for video content
- git: Version control system for repository management
- python: Core runtime environment for Python code

## FAQ
<details>
	
* Can I change subtitle language or turn them off? - No, the subtitles are baked into the video.
* Can I watch in french voice? - Yes, use `--vf`.
* Can I change dub language? - No.
* Can I change media source? - No (unless you can scrape that source yourself).
* Can I use vlc? - No only mpv.

**Note:** All features are documented in `animesama-cli --help`.

</details>

## Another language

* [ani-cli](https://github.com/pystardust/ani-cli): Japanese voice with English subtitles and English voice (allmanga)
* [GoAnime](https://github.com/alvarorichard/GoAnime): Japanese voice with Portuguese subtitles and Portuguese voice
* [doccli](https://github.com/TowarzyszFatCat/doccli): Japanese voice with Polish subtitles and Polish voice (docchi.pl)

### Original idea [ani-cli](https://github.com/pystardust/ani-cli)
