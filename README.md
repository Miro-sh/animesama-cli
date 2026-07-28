<div align="center">

# animesama-cli

Browse and watch anime from [anime-sama.si](https://anime-sama.si) directly in your terminal.

<a href="https://aur.archlinux.org/packages/animesama-cli"><img src="https://img.shields.io/aur/version/animesama-cli" alt="AUR version"></a>
<a href="https://pypi.org/project/animesama"><img src="https://img.shields.io/pypi/v/animesama" alt="PyPI version"></a>
<img src="https://img.shields.io/badge/platform-linux-90ee90" alt="Linux">
<img src="https://img.shields.io/badge/platform-windows-90ee90" alt="Windows">

</div>

## Demo

<div align="center">

![animesama-cli demo](./assets/demo.gif)

</div>

## Overview

animesama-cli is a terminal application for browsing and watching anime from [anime-sama.si](https://anime-sama.si). It provides catalog search, persistent watch history, and the weekly release schedule. Video playback is handled by [mpv](https://mpv.io).

## Features

- Full-text search of the anime-sama catalog
- Interactive TUI built with [Textual](https://textual.textualize.io/), with a standard CLI fallback
- Watch history stored in SQLite, with resume support
- Weekly release schedule from anime-sama
- Upcoming episodes from animecountdown.com
- French dub (VF) and Japanese audio with French subtitles (VOSTFR)
- Linux and Windows support; AUR package available for Arch Linux

## Installation

Every release is automatically published to all of these package managers:

| Platform | Package manager | Install command |
|----------|-----------------|-----------------|
| Debian / Ubuntu | apt ([own repository](#debian--ubuntu)) | `sudo apt install animesama-cli` |
| Fedora / RHEL | dnf ([own repository](#fedora--rhel)) | `sudo dnf install animesama-cli` |
| Arch Linux | [AUR](https://aur.archlinux.org/packages/animesama-cli) | `yay -S animesama-cli` |
| macOS | [Homebrew](https://github.com/Miro-sh/homebrew-tap) | `brew install Miro-sh/tap/animesama` |
| Any Linux / macOS | [pipx](https://pipx.pypa.io) ([PyPI](https://pypi.org/project/animesama)) | `pipx install animesama` |
| Windows | [Install script](#windows) | See below |

The apt/dnf packages and the Homebrew formula pull in `mpv` and Python automatically. With pipx, install `mpv` through your package manager first.

### Debian / Ubuntu

Add the GPG key and the repository, then install:

```sh
curl -fsSL https://miro-sh.github.io/animesama-cli/animesama.gpg | sudo gpg --dearmor -o /usr/share/keyrings/animesama.gpg
echo "deb [signed-by=/usr/share/keyrings/animesama.gpg] https://miro-sh.github.io/animesama-cli/apt stable main" | sudo tee /etc/apt/sources.list.d/animesama.list
sudo apt update && sudo apt install animesama-cli
```

### Fedora / RHEL

Add the repository file, then install:

```sh
sudo curl -fsSL -o /etc/yum.repos.d/animesama.repo https://miro-sh.github.io/animesama-cli/rpm/animesama.repo
sudo dnf install animesama-cli
```

dnf will ask you to trust the GPG key (fingerprint `035B2D3F0897E499`) on first install.

### Arch Linux

```sh
yay -S animesama-cli
```

### macOS

```sh
brew install Miro-sh/tap/animesama
```

### pipx (any distribution)

```sh
pipx install animesama
```

### Windows

Run the following command in PowerShell (no administrator rights required):

```powershell
irm "https://raw.githubusercontent.com/Miro-sh/animesama-cli/refs/heads/master/install_windows.bat" -OutFile install.bat; .\install.bat
```

The script installs the application via [pipx](https://pipx.pypa.io) and downloads mpv. Restart your terminal after installation, then run `animesama-cli`.

## Usage

| Command | Description |
|---------|-------------|
| `animesama-cli` | Launch the TUI (falls back to CLI if Textual is not installed) |
| `animesama-cli --cli` | Force CLI mode |
| `animesama-cli naruto` | Search directly |
| `animesama-cli --vf naruto` | Search French dub only |
| `animesama-cli -c` | Show watch history |
| `animesama-cli -cf` | History with last-episode check |
| `animesama-cli -p` | Weekly schedule |
| `animesama-cli -up` | Upcoming episodes |
| `animesama-cli --debug naruto` | Search with debug output |
| `animesama-cli -h` | Show all options |

The watch history is stored at `~/.local/share/animesama-cli/history.db` and can be opened with any SQLite browser.

## Uninstall

<details>

**apt / dnf:**

```sh
sudo apt remove animesama-cli    # Debian/Ubuntu
sudo dnf remove animesama-cli    # Fedora
```

**AUR:**

```sh
yay -R animesama-cli
```

**Homebrew:**

```sh
brew uninstall animesama
```

**pipx (Linux and Windows):**

```sh
pipx uninstall animesama
```

**Windows (mpv installed by the script):**

```batch
rd /s /q "%USERPROFILE%\AnimeSamaCLI"
```

**Old manual installs (before 1.0.7):**

```sh
sudo rm /usr/local/bin/animesama-cli
rm -rf ~/animesama-cli
rm -rf ~/.local/share/animesama-venv
```

</details>

## Dependencies

| Category | Packages |
|----------|----------|
| Python   | `requests`, `beautifulsoup4`, `textual` (optional, for the TUI), `windows-curses` (Windows only) |
| System   | `mpv`, `git`, `python3` |

Built-in Python modules used: `sqlite3`, `re`, `json`, `sys`, `os`, `time`, `datetime`, `locale`, `pathlib`, `subprocess`, `asyncio`.

## FAQ

<details>
  <summary>Click to expand</summary>
  <br>

**Can I change or disable subtitles?** No. Subtitles are embedded in the video stream.

**Can I watch in French?** Yes. Use `--vf` when searching.

**Can I switch the audio language?** No. The site only provides French dub and Japanese audio with French subtitles.

**Can I use a different video source?** No, unless you write your own scraper.

**Can I use VLC?** No. Only `mpv` is supported.

**Where can I find all the options?** Run `animesama-cli --help`.

</details>

## Related projects

- [ani-cli](https://github.com/pystardust/ani-cli): Japanese audio, English subtitles (4anime, gogoanime, allmanga). animesama-cli was inspired by this project.
- [GoAnime](https://github.com/alvarorichard/GoAnime): Japanese audio, Portuguese subtitles
- [doccli](https://github.com/TowarzyszFatCat/doccli): Japanese audio, Polish subtitles (docchi.pl)

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](./contribution.md) before opening an issue or pull request. You can also join the [Discord server](https://discord.gg/MwHAXPpJ8C) to discuss the project.

## Disclaimer

This project only fetches publicly available content and hosts nothing itself. Users are responsible for how they use it. See [DISCLAIMER.md](./disclaimer.md) for details.
