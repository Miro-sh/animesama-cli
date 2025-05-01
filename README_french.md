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
Un outil en ligne de commande pour parcourir et regarder des animes depuis <a href="https://anime-sama.fr">anime-sama.fr</a> (en version française et avec sous-titres).
</h3>

<h1 align="center">
	Démonstration
</h1>

[showcase.webm](https://user-images.githubusercontent.com/44473782/224679247-0856e652-f187-4865-bbcf-5a8e5cf830da.webm)

## Sommaire

- [Installation](#installation)
  - [Linux](#première-installation)
  - [Windows](#seconde-installation)
- [Désinstallation](#désinstallation)
- [Dépendances](#dépendances)
- [FAQ](#faq)
  - [Autres Langues](#autres-langues)
- [Guide de Contribution](./contribution.md)
- [Avertissement](./disclaimer.md)

## Installation

[![État des paquets](https://repology.org/badge/vertical-allrepos/animesama-cli.svg?minversion=1.0.0)](https://repology.org/project/animesama-cli/versions)

### Première Installation

*Ces plateformes sont parfaitement prises en charge et sont utilisées par les mainteneurs et une grande partie des utilisateurs.*

<details><summary><b>Linux</b></summary>



*Assurez-vous d'avoir installé toutes les dépendances nécessaires. Pour les distributions basées sur Debian, vous aurez besoin de curl, python3 et mpv. Le script d'installation s'occupera du reste du processus de configuration.*

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

### Seconde Installation

<details><summary><b>Windows</b></summary>

Ouvrez PowerShell (pas besoin de permissions administrateur) et collez la commande ci-dessous
```powershell
irm "https://raw.githubusercontent.com/DictateurMiro/animesama-cli/refs/heads/master/setup_animesama_cli.bat" -OutFile install.bat; .\install.bat
```

</details>

## Désinstallation

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

## Dépendances

### Dépendances Python
- requests: Bibliothèque HTTP pour effectuer des requêtes web
- beautifulsoup4 (bs4): Parseur HTML/XML pour le web scraping
- sqlite3: Module intégré pour les opérations de base de données SQLite
- curses: Bibliothèque d'interface utilisateur en mode terminal
- windows-curses: Version Windows de curses
- re: Module intégré pour les opérations avec les expressions régulières
- json: Module intégré pour l'analyse/génération JSON
- sys: Module intégré pour l'interaction avec l'interpréteur
- os: Module intégré pour les fonctionnalités liées au système d'exploitation
- time: Module intégré pour les fonctions temporelles
- datetime: Module intégré pour la manipulation des dates/heures
- locale: Module intégré pour la prise en charge de la localisation
- pathlib: Module intégré pour les opérations sur les chemins du système de fichiers

### Dépendances Système
- mpv: Lecteur multimédia pour le contenu vidéo
- git: Système de contrôle de version pour la gestion des dépôts
- python: Environnement d'exécution principal pour le code Python

## FAQ
<details>
	
* Puis-je changer la langue des sous-titres ou les désactiver ? - Non, les sous-titres sont intégrés dans la vidéo.
* Puis-je regarder en voix française ? - Oui, utilisez `--vf`.
* Puis-je changer la langue du doublage ? - Non.
* Puis-je changer la source des médias ? - Non (sauf si vous pouvez extraire cette source vous-même).
* Puis-je utiliser VLC ? - Non, uniquement mpv.

**Note :** Toutes les fonctionnalités sont documentées dans `animesama-cli --help`.

</details>

## Autres Langues

* [ani-cli](https://github.com/pystardust/ani-cli) : Voix japonaise avec sous-titres anglais et voix anglaise (allmanga)
* [GoAnime](https://github.com/alvarorichard/GoAnime) : Voix japonaise avec sous-titres portugais et voix portugaise
* [doccli](https://github.com/TowarzyszFatCat/doccli) : Voix japonaise avec sous-titres polonais et voix polonaise (docchi.pl)

### Idée originale [ani-cli](https://github.com/pystardust/ani-cli)
