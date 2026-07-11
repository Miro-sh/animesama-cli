<p align="center">
  <br>
  <a href="#-linux"><img src="https://img.shields.io/badge/os-linux-90ee90" alt="Linux"></a>
  <a href="#-windows"><img src="https://img.shields.io/badge/os-windows-90ee90" alt="Windows"></a>
  <br><br>
</p>

<p align="center">
  <sub>Ce README est aussi dispo en &#127482;&#127480; <a href="README.md">Anglais</a></sub>
</p>

<p align="center">
  <img src="https://repology.org/badge/vertical-allrepos/animesama-cli.svg?minversion=1.0.5" alt="Statut des paquets">
</p>

---

## &#127916; C'est quoi ?

Un outil en terminal pour parcourir et regarder des animes depuis [anime-sama.fr](https://anime-sama.fr). Il scrape le catalogue, permet de chercher, garde un historique, et affiche le planning des sorties.

La lecture passe par `mpv`. Pas de navigateur, pas de pubs, pas de bloat.

## &#127775; Fonctionnalités

- Recherche sur tout le catalogue [anime-sama.fr](https://anime-sama.fr) direct depuis le terminal
- Deux interfaces : un TUI propre avec [Textual](https://textual.textualize.io/) et un fallback CLI classique
- Historique de visionnage en SQLite (reprends où tu t'es arrêté, vois quels animes sont finis)
- Planning hebdomadaire des sorties récupéré du site
- Liste des prochains épisodes via animecountdown.com
- Version française (VF) et version originale sous-titrée (VOSTFR)
- Tourne sur Linux et Windows
- Paquet AUR pour Arch Linux (`animesama-cli`)

## &#9992;&#65039; Démarrage rapide

### &#128187; Linux

#### Debian / Ubuntu
Assure-toi d'avoir `curl`, `python3` et `mpv`. Le script gère le reste.

```sh
sudo apt-get install curl -y
curl -fsSL https://raw.githubusercontent.com/DictateurMiro/animesama-cli/master/install.sh -o /tmp/animesama-install.sh && chmod +x /tmp/animesama-install.sh && sh /tmp/animesama-install.sh
```

#### Arch Linux
```sh
yay -S animesama-cli
```

### &#128187; Windows

Ouvre PowerShell (pas besoin d'admin) et colle ceci :

```powershell
irm "https://raw.githubusercontent.com/DictateurMiro/animesama-cli/refs/heads/master/setup_animesama_cli.bat" -OutFile install.bat; .\install.bat
```

Ça installe les dépendances Python, récupère mpv, et crée les scripts de lancement. Une fois fini, ferme et rouvre ton terminal, puis tape `animesama-cli`.

## &#128161; Utilisation

```sh
animesama-cli                  # Lance le TUI (ou CLI si Textual n'est pas installé)
animesama-cli --cli            # Force le mode CLI
animesama-cli naruto           # Recherche directe
animesama-cli --vf naruto      # Recherche en VF uniquement
animesama-cli -c               # Affiche l'historique
animesama-cli -cf              # Historique avec vérification du dernier épisode
animesama-cli -p               # Planning hebdomadaire
animesama-cli -up              # Prochains épisodes à sortir
animesama-cli --debug naruto   # Recherche avec logs de debug
animesama-cli -h               # Toutes les options
```

L'historique est stocké dans `~/.local/share/animesama-cli/history.db`. Tu peux l'ouvrir avec n'importe quel navigateur SQLite.

## &#128295; Désinstallation

<details>

**AUR :**
```sh
yay -R animesama-cli
```

**Linux (install manuelle) :**
```sh
sudo rm /usr/local/bin/animesama-cli
rm -rf ~/animesama-cli
rm -rf ~/.local/share/animesama-venv
```

**Windows :**
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

## &#128218; Dépendances

| Catégorie | Paquets |
|-----------|---------|
| Python    | `requests`, `beautifulsoup4`, `textual` (optionnel pour le TUI), `windows-curses` (Windows seulement) |
| Système   | `mpv`, `git`, `python3` |

Modules Python intégrés utilisés : `sqlite3`, `re`, `json`, `sys`, `os`, `time`, `datetime`, `locale`, `pathlib`, `subprocess`, `asyncio`.

## &#10067; FAQ

<details>
  <summary>Clique pour déplier</summary>
  <br>

**Je peux changer ou désactiver les sous-titres ?** Non. Les sous-titres sont incrustés dans la vidéo.

**Je peux regarder en VF ?** Oui. Utilise `--vf` dans la recherche.

**Je peux changer la langue audio ?** Non. Le site propose uniquement la VF et la VO avec sous-titres français.

**Je peux utiliser une autre source ?** Non, sauf si tu codes ton propre scraper.

**Je peux utiliser VLC ?** Non. Seul `mpv` est supporté.

**Où trouver toutes les options ?** `animesama-cli --help`

</details>

## &#127757; Outils similaires dans d'autres langues

- [ani-cli](https://github.com/pystardust/ani-cli) : VO japonaise, sous-titres anglais (4anime, gogoanime, allmanga)
- [GoAnime](https://github.com/alvarorichard/GoAnime) : VO japonaise, sous-titres portugais
- [doccli](https://github.com/TowarzyszFatCat/doccli) : VO japonaise, sous-titres polonais (docchi.pl)

Ce projet est inspiré de [ani-cli](https://github.com/pystardust/ani-cli).

## &#129309; Contribuer

Voir [CONTRIBUTING.md](./contribution.md) pour les règles sur les PRs et les issues. Si tu veux aider sans coder, rejoins le [Discord](https://discord.gg/MwHAXPpJ8C), mets une étoile au repo, ou parle-en autour de toi.

## &#9888;&#65039; Avertissement

Voir [DISCLAIMER.md](./disclaimer.md).

En résumé : ceci est un navigateur pour ton terminal. Il récupère du contenu disponible publiquement. Ce que tu en fais te regarde. Aucun contenu n'est hébergé sur ce repo.
