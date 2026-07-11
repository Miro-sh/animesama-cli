<p align="center">
  <br>
  <a href="#-linux"><img src="https://img.shields.io/badge/os-linux-90ee90" alt="Linux"></a>
  <a href="#-windows"><img src="https://img.shields.io/badge/os-windows-90ee90" alt="Windows"></a>
  <br><br>
</p>

<p align="center">
  <sub>This README is also available in &#127467;&#127479; <a href="README_french.md">French</a></sub>
</p>

<p align="center">
  <img src="https://repology.org/badge/vertical-allrepos/animesama-cli.svg?minversion=1.0.5" alt="Packaging status">
</p>

---

## &#127916; What is this?

A terminal app to browse and watch anime from [anime-sama.fr](https://anime-sama.fr). It scrapes the catalog, lets you search, keeps a watch history, and checks the weekly release schedule.

All video playback goes through `mpv`. No browser, no ads, no clutter.

## &#127775; Features

- Search the entire [anime-sama.fr](https://anime-sama.fr) catalog right from your terminal
- Two interfaces: a sleek TUI built with [Textual](https://textual.textualize.io/) and a plain CLI fallback
- Watch history with SQLite (pick up where you left off, see which shows you've finished)
- Weekly release schedule pulled from the site
- Upcoming episode list from animecountdown.com
- French dub (VF) and original Japanese with French subs (VOSTFR)
- Works on Linux and Windows
- Arch Linux AUR package (`animesama-cli`)

## &#9992;&#65039; Quick start

### &#128187; Linux

#### Debian / Ubuntu
Make sure `curl`, `python3`, and `mpv` are installed. The script handles the rest.

```sh
sudo apt-get install curl -y
curl -fsSL https://raw.githubusercontent.com/DictateurMiro/animesama-cli/master/install.sh -o /tmp/animesama-install.sh && chmod +x /tmp/animesama-install.sh && sh /tmp/animesama-install.sh
```

#### Arch Linux
```sh
yay -S animesama-cli
```

### &#128187; Windows

Open PowerShell (admin not required) and paste this:

```powershell
irm "https://raw.githubusercontent.com/DictateurMiro/animesama-cli/refs/heads/master/setup_animesama_cli.bat" -OutFile install.bat; .\install.bat
```

This grabs Python deps, fetches mpv, and sets up the launcher scripts. After it finishes, open a fresh terminal and run `animesama-cli`.

## &#128161; Usage

```sh
animesama-cli                  # Launch the TUI (or CLI if Textual is not installed)
animesama-cli --cli            # Force CLI mode
animesama-cli naruto           # Search directly
animesama-cli --vf naruto      # Search French dub only
animesama-cli -c               # Show watch history
animesama-cli -cf              # History with last-episode check
animesama-cli -p               # Weekly schedule
animesama-cli -up              # Upcoming episodes
animesama-cli --debug naruto   # Search with debug output
animesama-cli -h               # Show all options
```

The history lives at `~/.local/share/animesama-cli/history.db`. You can open it with any SQLite browser.

## &#128295; Uninstall

<details>

**AUR:**
```sh
yay -R animesama-cli
```

**Linux (manual install):**
```sh
sudo rm /usr/local/bin/animesama-cli
rm -rf ~/animesama-cli
rm -rf ~/.local/share/animesama-venv
```

**Windows:**
```batch
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

## &#128218; Dependencies

| Category | Packages |
|----------|----------|
| Python   | `requests`, `beautifulsoup4`, `textual` (optional for TUI), `windows-curses` (Windows only) |
| System   | `mpv`, `git`, `python3` |

Built-in Python modules used: `sqlite3`, `re`, `json`, `sys`, `os`, `time`, `datetime`, `locale`, `pathlib`, `subprocess`, `asyncio`.

## &#10067; FAQ

<details>
  <summary>Click to expand</summary>
  <br>

**Can I change or disable subtitles?** No. Subs are baked into the video stream.

**Can I watch in French?** Yes. Use `--vf` or `--vf` in search.

**Can I switch audio language?** No. The site only hosts French dub and Japanese with French subtitles.

**Can I use a different video source?** No, unless you build your own scraper.

**Can I use VLC?** No. Only `mpv` is supported.

**Where do I find all the options?** `animesama-cli --help`

</details>

## &#127757; Tools in other languages

- [ani-cli](https://github.com/pystardust/ani-cli) : Japanese audio, English subs (4anime, gogoanime, allmanga)
- [GoAnime](https://github.com/alvarorichard/GoAnime) : Japanese audio, Portuguese subs
- [doccli](https://github.com/TowarzyszFatCat/doccli) : Japanese audio, Polish subs (docchi.pl)

This project was inspired by [ani-cli](https://github.com/pystardust/ani-cli).

## &#129309; Contributing

See [CONTRIBUTING.md](./contribution.md) for the rules on PRs and issues. If you want to help but not write code, join the [Discord](https://discord.gg/MwHAXPpJ8C), star the repo, or just spread the word.

## &#9888;&#65039; Disclaimer

See [DISCLAIMER.md](./disclaimer.md).

The short version: this is a browser for your terminal. It fetches publicly available content. What you do with it is up to you. No content is hosted on this repo.
