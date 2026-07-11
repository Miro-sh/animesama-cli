#!/usr/bin/env python3

import requests
import subprocess
import re
import sys
import json
import sqlite3
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import os
import time
from datetime import datetime
import locale
import pathlib
import argparse
import asyncio

try:
    from textual.app import App, ComposeResult
    from textual.widgets import Header, Footer, Button, Static, ListView, ListItem, Label, Input
    from textual.containers import Container
    from textual.reactive import reactive
    from textual.message import Message
    from textual.screen import Screen
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False

HEADERS_BASE = {
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:134.0) Gecko/20100101 Firefox/134.0",
    "accept-language": "en-US,en;q=0.5",
    "connection": "keep-alive"
}

MENU_ITEMS = [
    ("Recherche d'anime", "search"),
    ("Historique", "history"),
    ("Planning", "planning"),
    ("À venir", "upcoming")
]


FALLBACK_DOMAIN = "anime-sama.to"

def resolve_final_domain(domain):
    try:
        resp = requests.head(f"https://{domain}", headers=HEADERS_BASE, timeout=5, allow_redirects=True)
        final = urlparse(resp.url).hostname
        return final if final else domain
    except requests.RequestException:
        return domain

def get_current_domain_name():
    resolved = None
    try:
        response = requests.get("https://anime-sama.pw/", headers=HEADERS_BASE, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        for tag in soup.find_all(['button', 'a']):
            text = tag.get_text(strip=True)
            if 'anime-sama' in text and '.' in text and 'pw' not in text:
                resolved = text
                break
            href = tag.get('href')
            if href and 'anime-sama' in href and 'pw' not in href:
                match = re.search(r'https?://([^/]+)', href)
                if match:
                    resolved = match.group(1)
                    break
    except Exception:
        pass

    if resolved:
        final = resolve_final_domain(resolved)
        if final != resolved:
            resolved = final

    if not resolved:
        resolved = FALLBACK_DOMAIN

    return resolved


DOMAIN = get_current_domain_name()
if not DOMAIN:
    DOMAIN = FALLBACK_DOMAIN


def check_domain_access():
    try:
        response = requests.head(f"https://{DOMAIN}", headers=HEADERS_BASE, timeout=5, allow_redirects=True)
        return response.status_code == 200
    except requests.RequestException:
        return False

IS_DOMAIN_AVAILABLE = check_domain_access()

def get_db_path():
    db_dir = os.path.expanduser("~/.local/share/animesama-cli")
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, "history.db")

def init_db():
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        anime_name TEXT NOT NULL,
        episode TEXT NOT NULL,
        saison TEXT NOT NULL,
        url TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    conn.commit()
    conn.close()

def add_to_history(anime_name, episode, saison, url, debug=False):
    try:
        init_db()
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM history WHERE anime_name = ? AND saison = ?", 
            (anime_name, saison)
        )
        existing_entry = cursor.fetchone()
        if existing_entry:
            cursor.execute(
                "UPDATE history SET episode = ?, timestamp = CURRENT_TIMESTAMP WHERE id = ?",
                (episode, existing_entry[0])
            )
            if debug:
                print("[DEBUG] Historique mis à jour avec succès")
            else:
                print("✓ Historique mis à jour avec succès")
        else:
            cursor.execute(
                "INSERT INTO history (anime_name, episode, saison, url) VALUES (?, ?, ?, ?)",
                (anime_name, episode, saison, url)
            )
            if debug:
                print("[DEBUG] Ajouté à l'historique avec succès")
            else:
                print("✓ Ajouté à l'historique avec succès")
        conn.commit()
        conn.close()
    except Exception as e:
        if debug:
            print(f"[DEBUG] Erreur lors de l'ajout à l'historique: {e}")
        else:
            print(f"✗ Erreur lors de l'ajout à l'historique")

def get_history_entries():
    db_path = get_db_path()
    if not os.path.exists(db_path):
        return []
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, anime_name, episode, saison, url FROM history ORDER BY timestamp DESC")
    entries = cursor.fetchall()
    conn.close()
    return entries

def delete_history_entry(entry_id):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("DELETE FROM history WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()

def get_seasons(html_content):
    seasons = []
    pattern = r'panneauAnime\("([^"]+)",\s*"([^"]+)"\)'
    soup = BeautifulSoup(html_content, 'html.parser')
    season_buttons = soup.find_all('button', {'onclick': True})
    season_divs = soup.find_all('div', class_=lambda x: x and 'saison' in x.lower())
    matches = re.findall(pattern, html_content)
    if not matches:
        return []
    for name, path in matches:
        if "film" not in name.lower() and name.lower() != "nom":
            seasons.append({
                'name': name,
                'url': path
            })
    return seasons

def get_episode_list(url):
    url = url.replace('https://', '')
    headers = {
        "host": DOMAIN,
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:134.0) Gecko/134.0",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "accept-language": "en-US,en;q=0.5",
        "connection": "keep-alive",
        "upgrade-insecure-requests": "1",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "sec-fetch-user": "?1"
    }
    try:
        response = requests.get(f"https://{url}", headers=headers)
        content = response.text
        pattern = r'episodes\.js\?filever=(\d+)'
        match = re.search(pattern, content)
        if match:
            filever = match.group(1)
            return filever
        return None
    except Exception as e:
        print(f"Erreur lors de la requête : {str(e)}")
        return None

class AnimeDownloader:
    def __init__(self, debug=False):
        self.session = requests.Session()
        self.session.headers.update(HEADERS_BASE)
        self.debug = debug

    def debug_print(self, *args, **kwargs):
        if self.debug:
            print("[DEBUG]", *args, **kwargs)

    def get_anime_episode(self, complete_url, filever):
        complete_url = complete_url.replace('https://', '')
        url = f"https://{complete_url}/episodes.js"
        try:
            response = self.session.get(url, params={"filever": filever})
            response.raise_for_status()
            content = response.text
            embed_links = {}
            matches = re.finditer(r"var eps\d+\s*=\s*\[([^\]]+)\]", content)
            for ep_var_match in matches:
                urls_block = ep_var_match.group(1)
                vid_urls = re.findall(r"'([^']+)'", urls_block)
                for i, vid_url in enumerate(vid_urls, 1):
                    if str(i) not in embed_links:
                        embed_links[str(i)] = vid_url
            return embed_links
        except requests.RequestException as e:
            print(f"Erreur lors de la récupération des épisodes : {e}")
            return {}

    def get_video_url(self, video_id):
        try:
            print(f"Tentative de recuperation de la video...")

            if 'sibnet.ru' in video_id:
                vid_match = re.search(r'videoid=(\d+)', video_id)
                if vid_match:
                    return self._get_sibnet_url(vid_match.group(1))

            if 'vidmoly.to' in video_id:
                video_id = video_id.replace('vidmoly.to', 'vidmoly.biz')
            video_id = video_id.replace('vidmoly.net', 'vidmoly.biz')

            response = self.session.get(video_id, headers={
                **HEADERS_BASE,
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "referer": f"https://{DOMAIN}/",
            })
            response.raise_for_status()
            html_content = response.text

            match = re.search(r"file:\s*'([^']+\.m3u8[^']*)'", html_content)
            if match:
                m3u8_url = match.group(1).replace('&amp;', '&')
                print(f"URL m3u8 trouvee.")
                return m3u8_url

            match = re.search(r'sources:\s*\[\s*\{\s*file:\s*"([^"]+)"', html_content)
            if match:
                m3u8_url = match.group(1).replace('&amp;', '&')
                print(f"URL m3u8 trouvee.")
                return m3u8_url

            match = re.search(r'(https?://[^\s"\']+\.mp4[^\s"\']*)', html_content)
            if match:
                mp4_url = match.group(1).replace('&amp;', '&')
                print(f"URL mp4 directe trouvee.")
                return mp4_url

            print(f"Erreur : aucun flux video trouve dans l'embed ({len(html_content)} octets)")
            return None
        except requests.RequestException as e:
            print(f"Erreur lors de la recuperation de l'URL video : {e}")
            return None

    def _get_sibnet_url(self, video_id):
        try:
            url = "https://video.sibnet.ru/shell.php"
            response = self.session.get(url, params={"videoid": video_id})
            response.raise_for_status()
            html_content = response.text
            match = re.search(r'player\.src\(\[\{src: "/v/([^/]+)/', html_content)
            if match:
                video_hash = match.group(1)
                url_sibnet = f"https://video.sibnet.ru/v/{video_hash}/{video_id}.mp4"
                headers_sibnet = {
                    **HEADERS_BASE,
                    "range": "bytes=0-",
                    "accept-encoding": "identity",
                    "referer": "https://video.sibnet.ru/",
                }
                response_sibnet = self.session.get(url_sibnet, headers=headers_sibnet, allow_redirects=False)
                if response_sibnet.status_code == 302:
                    print(f"URL sibnet trouvee.")
                    return response_sibnet.headers['Location']
                else:
                    print(f"Status code sibnet inattendu : {response_sibnet.status_code}")
            else:
                print("Pattern sibnet non trouve dans le HTML")
            return None
        except requests.RequestException as e:
            print(f"Erreur sibnet : {e}")
            return None
        except requests.RequestException as e:
            print(f"Erreur lors de la récupération de l'URL vidéo : {e}")
            return None

    def get_catalogue(self, query="", vf=False): 
        try:
            url = f"https://{DOMAIN}/catalogue/"
            headers = {
                "host": DOMAIN,
                "connection": "keep-alive",
                "sec-ch-ua": "\"Not A(Brand\";v=\"8\", \"Chromium\";v=\"132\", \"Google Chrome\";v=\"132\"",
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": "\"Windows\"",
                "upgrade-insecure-requests": "1",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "sec-fetch-site": "same-origin",
                "sec-fetch-mode": "navigate",
                "sec-fetch-user": "?1",
                "sec-fetch-dest": "document",
                "referer": f"https://{DOMAIN}/catalogue/",
                "accept-language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7"
            }
            querystring = {"search": query, "type[]": "Anime"}
            if vf:
                querystring["langue[]"] = "VF"
            self.debug_print(f"Envoi requête GET vers: {url}")
            self.debug_print(f"Headers: {headers}")
            self.debug_print(f"Querystring: {querystring}")
            response = self.session.get(url, headers=headers, params=querystring)
            response.raise_for_status()
            self.debug_print(f"Status code: {response.status_code}")
            self.debug_print(f"Réponse brute: {response.text}")
            soup = BeautifulSoup(response.text, 'html.parser')
            animes = []
            urls = []
            seen_urls = set()
            for card in soup.find_all('a', href=True):
                href = card['href']
                if '/catalogue/' not in href or href in seen_urls:
                    continue
                if href == '/catalogue/' or href == '/catalogue':
                    continue
                titre_tag = card.find('h2', class_='card-title')
                if not titre_tag:
                    titre_tag = card.find('h1', class_='text-white font-bold uppercase text-md line-clamp-2')
                if titre_tag:
                    titre = titre_tag.text.strip()
                    if titre:
                        seen_urls.add(href)
                        animes.append(titre)
                        urls.append(href)
            if vf:
                urls = [link.replace("vostfr", "vf") for link in urls]
            self.debug_print(f"Nombre de titres trouvés: {len(animes)}")
            self.debug_print(f"Titres trouvés: {animes}")
            return animes, urls
        except requests.RequestException as e:
            print(f"Erreur lors de la récupération du catalogue : {e}")
            self.debug_print(f"Exception complète: {str(e)}")
            return [], []

def display_history(full_check=False):
    init_db()
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("SELECT id, anime_name, episode, saison, url FROM history ORDER BY timestamp DESC")
    history_entries = cursor.fetchall()
    conn.close()
    if not history_entries:
        print("Aucun historique trouvé.")
        return
    print("\nHistorique :")
    for i, entry in enumerate(history_entries, 1):
        entry_id, anime_name, episode, saison, url = entry
        is_last = False
        match = re.search(r'(\d+)$', episode)
        if match and full_check:
            current_ep = int(match.group(1))
            filever = get_episode_list(url)
            if filever:
                episodes = AnimeDownloader(debug=False).get_anime_episode(url, filever)
                if episodes:
                    ep_keys_int = [int(e) for e in episodes.keys() if e.isdigit()]
                    if ep_keys_int and current_ep == max(ep_keys_int):
                        is_last = True
        line = f"{i}. {anime_name} - {episode} - {saison}"
        if is_last:
            line += " - Dernier épisode"
        print(line)
    print("0. Retour")
    choix = input("Numéro à relire, ou 'd' suivi du numéro pour supprimer (ex: d2), ou 0 pour retour : ").strip()
    if choix == "0":
        return
    if choix.startswith('d') and choix[1:].isdigit():
        idx = int(choix[1:]) - 1
        if 0 <= idx < len(history_entries):
            entry_id = history_entries[idx][0]
            conn = sqlite3.connect(get_db_path())
            cursor = conn.cursor()
            cursor.execute("DELETE FROM history WHERE id = ?", (entry_id,))
            conn.commit()
            conn.close()
            print("Entrée supprimée.")
        else:
            print("Numéro invalide.")
        return
    if choix.isdigit():
        idx = int(choix) - 1
        if 0 <= idx < len(history_entries):
            entry = history_entries[idx]
            anime_name, episode, saison, url = entry[1:5]
            print(f"Lecture de {anime_name} - {episode} - {saison}")
            match = re.search(r'(\d+)$', episode)
            if match:
                current_ep = int(match.group(1))
            else:
                print("Impossible de déterminer l'épisode courant.")
                return
            filever = get_episode_list(url)
            if not filever:
                print("Impossible de récupérer la liste des épisodes.")
                return
            downloader = AnimeDownloader(debug=False)
            episodes = downloader.get_anime_episode(url, filever)
            if not episodes:
                print("Aucun épisode trouvé.")
                return
            ep_keys = list(episodes.keys())
            ep_keys_int = [int(e) for e in ep_keys if e.isdigit()]
            ep_keys_int.sort()
            next_ep = None
            for ep in ep_keys_int:
                if ep > current_ep:
                    next_ep = ep
                    break
            if next_ep is None:
                print(f"Vous avez déjà vu le dernier épisode : {anime_name} - Episode {current_ep} - {saison} - Dernier épisode (déjà vu)")
                return
            video_id = episodes[str(next_ep)]
            print(f"Récupération de l'épisode {next_ep}...")
            video_url = downloader.get_video_url(video_id)
            if not video_url:
                print("Impossible de récupérer l'URL de la vidéo.")
                return
            if video_url.startswith('//'):
                video_url = 'https:' + video_url
            print(f"Lecture de la vidéo avec mpv...")
            try:
                subprocess.run(['mpv', video_url, '--fullscreen'], check=True)
                add_to_history(
                    anime_name=anime_name,
                    episode=f"Episode {next_ep}",
                    saison=saison,
                    url=url,
                    debug=False
                )
            except FileNotFoundError:
                print("Erreur : mpv n'est pas installé.")
            except Exception as e:
                print(f"Erreur lors de la lecture : {e}")
        else:
            print("Numéro invalide.")
        return
    print("Entrée non reconnue.")

def afficher_planning():
    print("\n--- Planning des animes (texte) ---")
    url = f"https://{DOMAIN}/planning/"
    headers = HEADERS_BASE.copy()
    response = requests.get(url, headers=headers)
    html_content = response.text
    day_pattern = r'<h2 class="titreJours[^>]*>([^<]+)</h2>'
    days = re.findall(day_pattern, html_content)
    planning = {day.strip(): [] for day in days}
    day_sections = re.split(day_pattern, html_content)
    for i in range(1, len(day_sections), 2):
        current_day = day_sections[i].strip()
        day_content = day_sections[i + 1]
        if current_day in planning:
            cards = re.findall(
                r'<a href="(/catalogue/[^"]+)"[^>]*>.*?<h3[^>]*>([^<]+)</h3>',
                day_content, re.DOTALL
            )
            if not cards:
                cards = re.findall(
                    r'<a href="(/catalogue/[^"]+)"[^>]*>.*?<img[^>]*alt="([^"]*)"',
                    day_content, re.DOTALL
                )
            for card_url, card_title in cards:
                planning[current_day].append((card_title.strip(), card_url.strip(), "", ""))
    days_list = list(planning.keys())
    for i, day in enumerate(days_list, 1):
        print(f"{i}. {day}")
    print("0. Retour")
    choix = input("Numéro du jour : ").strip()
    if choix == "0":
        return
    if not choix.isdigit() or int(choix) < 1 or int(choix) > len(days_list):
        print("Numéro invalide.")
        return
    selected_day = days_list[int(choix)-1]
    animes = planning[selected_day]
    if not animes:
        print("Aucun anime ce jour.")
        return
    for i, (title, url, time, version) in enumerate(animes, 1):
        print(f"{i}. {title}")
    print("0. Retour")
    choix = input("Numéro de l'anime : ").strip()
    if choix == "0":
        return
    if not choix.isdigit() or int(choix) < 1 or int(choix) > len(animes):
        print("Numéro invalide.")
        return
    selected_anime = animes[int(choix)-1]
    anime_url = f"https://{DOMAIN}{selected_anime[1]}"
    print(f"URL de la saison : {anime_url}")
    afficher_episodes_saison(anime_url, selected_anime[0], "")

def display_upcoming():
    print("\n--- Prochains épisodes à sortir (texte) ---")
    url = "https://animecountdown.com/upcoming"
    headers = HEADERS_BASE.copy()
    response = requests.get(url, headers=headers)
    html_content = response.text
    soup = BeautifulSoup(html_content, 'html.parser')
    anime_list = soup.find_all('a', class_='countdown-content-trending-item')
    display_items = []
    for anime in anime_list:
        anime_title = anime.find('countdown-content-trending-item-title').text.strip()
        anime_episode = anime.find('countdown-content-trending-item-desc').text.strip()
        display_items.append(f"{anime_title} - {anime_episode}")
    for i, item in enumerate(display_items, 1):
        print(f"{i}. {item}")
    print("0. Retour")
    input("Appuyez sur entrée pour revenir au menu principal.")

def display_help():
    help_text = """
Usage: anime [OPTIONS] [SEARCH_TERM]

Options:
    -h, --help      Affiche ce message d'aide
    -c, --continue  Affiche l'historique des animes regardés
    -f, --full      Active la vérification des derniers épisodes dans l'historique
    --vf            Recherche uniquement les animes en version française (VF)
    --debug         Active le mode debug pour plus d'informations
    -p, --planing   Affiche le planning des animes par jour
    -up, --upcoming Affiche les prochains épisodes à sortir
    -t, --textual   Force l'utilisation de l'interface TUI (même comportement par défaut)
    --cli           Force l'utilisation de l'interface en ligne de commande traditionnelle
    -cf, --check-final  Historique avec vérification du dernier épisode

Information:
    L'historique est stocké localement dans ~/.local/share/animesama-cli/history.db
    Par défaut, l'interface utilisateur Textual (TUI) est utilisée si disponible.

Examples:
    anime                  # Lance l'interface TUI (ou CLI si Textual n'est pas installé)
    anime --cli            # Force l'utilisation de l'interface CLI traditionnelle
    anime naruto           # Recherche directement "naruto" (dans l'interface par défaut)
    anime --cli naruto     # Recherche "naruto" en utilisant l'interface CLI
    anime -c               # Affiche l'historique
    anime -cf              # Affiche l'historique avec vérification des derniers épisodes
    anime --vf naruto      # Recherche "naruto" uniquement en VF
    anime --debug naruto   # Recherche "naruto" avec le mode debug
    anime -p               # Affiche le planning des animes par jour
    anime -up              # Affiche les prochains épisodes à sortir
    """
    print(help_text)

def afficher_episodes_saison(url, anime_name, version):
    filever = get_episode_list(url)
    if not filever:
        print("Impossible de récupérer la liste des épisodes.")
        return
    episodes = AnimeDownloader(debug=False).get_anime_episode(url, filever)
    if not episodes:
        print("Aucun épisode trouvé.")
        return
    print("\nÉpisodes :")
    ep_keys = list(episodes.keys())
    for i, ep in enumerate(ep_keys, 1):
        print(f"{i}. Episode {ep}")
    idx = input("Numéro de l'épisode à regarder : ").strip()
    if not idx.isdigit() or int(idx) < 1 or int(idx) > len(ep_keys):
        print("Sélection invalide.")
        return
    selected_ep = ep_keys[int(idx) - 1]
    video_id = episodes[selected_ep]
    print(f"Récupération de l'épisode {selected_ep}...")
    video_url = AnimeDownloader(debug=False).get_video_url(video_id)
    if not video_url:
        print("Impossible de récupérer l'URL de la vidéo.")
        return
    if video_url.startswith('//'):
        video_url = 'https:' + video_url
    print(f"Lecture de la vidéo avec mpv...")
    try:
        subprocess.run(['mpv', video_url, '--fullscreen'], check=True)
        saison = version
        url_lower = url.lower()
        if "saison" not in version.lower():
            match = re.search(r'/saison(\d+)', url_lower)
            if match:
                saison = f"Saison {match.group(1)}"
            elif "/oav" in url_lower or "/ova" in url_lower:
                saison = "OAV"
            elif "/film" in url_lower:
                saison = "Film"
            elif "/special" in url_lower:
                saison = "Special"
            else:
                saison = version
        if "vostfr" in url.lower():
            version_str = "VOSTFR"
        elif re.search(r'/vf/?', url.lower()):
            version_str = "VF"
        else:
            version_str = ""
        if version_str and version_str.lower() not in saison.lower():
            saison = f"{saison} - {version_str}"
        add_to_history(
            anime_name=anime_name,
            episode=f"Episode {selected_ep}",
            saison=saison,
            url=url,
            debug=False
        )
    except FileNotFoundError:
        print("Erreur : mpv n'est pas installé.")
    except Exception as e:
        print(f"Erreur lors de la lecture : {e}")

def cli_main(args):
    if args.help:
        display_help()
        return
    
    if args.planing:
        afficher_planning()
        return
    
    if args.upcoming:
        display_upcoming()
        return
    
    if args.continuer:
        display_history(args.full)
        return
    
    if not args.query:
        print("\nAnime-sama CLI (inspiré de ani-cli)")
        print("1. Recherche d'anime")
        print("2. Historique")
        print("3. Planning")
        print("4. À venir")
        print("5. Quitter")
        choix = input("Choix : ").strip()
        if choix == "1":
            query = input("Recherche : ").strip()
            if not query:
                print("Aucune recherche.")
                return
            args.query = [query]
        elif choix == "2":
            display_history(False)
            return
        elif choix == "3":
            afficher_planning()
            return
        elif choix == "4":
            display_upcoming()
            return
        else:
            print("Bye !")
            return
    
    query = " ".join(args.query)
    print(f"🔍 Recherche de : {query}")
    downloader = AnimeDownloader(debug=args.debug)
    animes, urls = downloader.get_catalogue(query, vf=args.vf)

    if not animes:
        print("Aucun anime trouvé.")
        return
    
    print("\nRésultats :")
    for i, anime in enumerate(animes, 1):
        print(f"{i}. {anime}")
    
    idx = input("Numéro de l'anime à sélectionner : ").strip()
    if not idx.isdigit() or int(idx) < 1 or int(idx) > len(animes):
        print("Sélection invalide.")
        return
    
    selected_anime = int(idx) - 1
    anime_url = urls[selected_anime]
    print(f"URL de l'anime : {anime_url}")
    response = requests.get(anime_url, headers=HEADERS_BASE)
    seasons = get_seasons(response.text)
    
    if not seasons:
        print("Aucune saison trouvée.")
        return
    
    print("\nSaisons :")
    for i, season in enumerate(seasons, 1):
        print(f"{i}. {season['name']}")
    
    idx = input("Numéro de la saison à sélectionner : ").strip()
    if not idx.isdigit() or int(idx) < 1 or int(idx) > len(seasons):
        print("Sélection invalide.")
        return
    
    selected_season = int(idx) - 1
    season_url = anime_url.rstrip('/') + '/' + seasons[selected_season]['url'].lstrip('/')
    if args.vf:
        season_url = season_url.replace("vostfr", "vf")
        print(f"URL corrigée pour la VF : {season_url}")
    
    print(f"URL de la saison : {season_url}")
    filever = get_episode_list(season_url)
    if not filever:
        print("Impossible de récupérer la liste des épisodes.")
        return
    
    episodes = downloader.get_anime_episode(season_url, filever)
    if not episodes:
        print("Aucun épisode trouvé.")
        return
    
    print("\nÉpisodes :")
    ep_keys = list(episodes.keys())
    for i, ep in enumerate(ep_keys, 1):
        print(f"{i}. Episode {ep}")
    
    idx = input("Numéro de l'épisode à regarder : ").strip()
    if not idx.isdigit() or int(idx) < 1 or int(idx) > len(ep_keys):
        print("Sélection invalide.")
        return
    
    selected_ep = ep_keys[int(idx) - 1]
    video_id = episodes[selected_ep]
    print(f"Récupération de l'épisode {selected_ep}...")
    video_url = downloader.get_video_url(video_id)
    
    if not video_url:
        print("Impossible de récupérer l'URL de la vidéo.")
        return
    
    if video_url.startswith('//'):
        video_url = 'https:' + video_url
    
    print(f"Lecture de la vidéo avec mpv...")
    try:
        subprocess.run(['mpv', video_url, '--fullscreen'], check=True)
        saison = seasons[selected_season]['name']
        if "saison" not in saison.lower():
            match = re.search(r'/saison(\d+)', season_url, re.IGNORECASE)
            if match:
                saison = f"Saison {match.group(1)}"
            else:
                saison = seasons[selected_season]['name']
        
        if "vostfr" in season_url.lower():
            version_str = "VOSTFR"
        elif re.search(r'/vf/?', season_url.lower()):
            version_str = "VF"
        else:
            version_str = ""
        
        if version_str and version_str.lower() not in saison.lower():
            saison = f"{saison} - {version_str}"
        
        add_to_history(
            anime_name=animes[selected_anime],
            episode=f"Episode {selected_ep}",
            saison=saison,
            url=season_url,
            debug=args.debug
        )
    except FileNotFoundError:
        print("Erreur : mpv n'est pas installé.")
    except Exception as e:
        print(f"Erreur lors de la lecture : {e}")

if TEXTUAL_AVAILABLE:
    class MenuSelect(Message):
        def __init__(self, sender, index):
            super().__init__()
            self.sender = sender
            self.index = index


    class MainMenu(Static):
        def compose(self) -> ComposeResult:
            items = [
                ListItem(Label(f"  {emoji}  {text}"))
                for (text, _), emoji in zip(MENU_ITEMS, ["🔍", "⏱ ", "📅", "🆕"])
            ]
            self.list_view = ListView(*items, id="menu-list")
            yield self.list_view

        def on_mount(self):
            self.list_view.index = 0

        def on_list_view_selected(self, event):
            self.app.post_message(MenuSelect(self, self.list_view.index))

    class HistoryScreen(Screen):
        def compose(self) -> ComposeResult:
            yield Label("📺  Historique", id="history-title")
            self.entries = get_history_entries()
            if not self.entries:
                yield Label("Aucun anime dans l'historique.\nLance un episode pour commencer.", id="history-empty")
                yield Label("[bold]Entrée[/] lancer   [bold]d[/] supprimer   [bold]q[/] retour", id="history-help")
                return
            items = []
            for i, entry in enumerate(self.entries, 1):
                anime_name, episode, saison = entry[1:4]
                label = f" {anime_name}  [dim]{episode}[/]  [italic $accent]{saison}[/]"
                items.append(ListItem(Label(label, markup=True)))
            self.list_view = ListView(*items, id="history-list")
            yield self.list_view
            self.status_label = Label("", id="history-help")
            yield self.status_label

        def on_mount(self):
            if hasattr(self, "list_view"):
                self.list_view.index = 0
                self.set_focus(self.list_view)
            self.update_help()

        def update_help(self, text=""):
            if not hasattr(self, "status_label"):
                return
            if text:
                self.status_label.update(text)
            else:
                self.status_label.update("[bold]Entrée[/] reprendre   [bold]d[/] supprimer   [bold]q[/] retour")

        def on_list_view_selected(self, event):
            if hasattr(self, "list_view") and event.control is self.list_view:
                idx = self.list_view.index
                if idx < 0 or idx >= len(self.entries):
                    return
                entry = self.entries[idx]
                anime_name, episode, saison, url = entry[1:5]
                import re
                match = re.search(r'(\d+)$', episode)
                if match:
                    current_ep = int(match.group(1))
                else:
                    self.update_help("[red]Impossible de determiner l'episode courant.[/]")
                    return
                filever = get_episode_list(url)
                if not filever:
                    self.update_help("[red]Impossible de recuperer la liste des episodes.[/]")
                    return
                episodes = AnimeDownloader().get_anime_episode(url, filever)
                if not episodes:
                    self.update_help("[red]Aucun episode trouve.[/]")
                    return
                ep_keys = list(episodes.keys())
                ep_keys_int = [int(e) for e in ep_keys if e.isdigit()]
                ep_keys_int.sort()
                next_ep = None
                for ep in ep_keys_int:
                    if ep > current_ep:
                        next_ep = ep
                        break
                if next_ep is None:
                    self.update_help("[bold]Deja au dernier episode.[/]")
                    return
                video_id = episodes[str(next_ep)]
                self.update_help(f"Recuperation de l'episode {next_ep}...")
                video_url = AnimeDownloader().get_video_url(video_id)
                if not video_url:
                    self.update_help("[red]Impossible de recuperer l'URL de la video.[/]")
                    return
                if video_url.startswith('//'):
                    video_url = 'https:' + video_url
                self.update_help(f"Lecture de l'episode {next_ep} avec mpv...")
                self.app.pop_screen()
                try:
                    subprocess.run(['mpv', video_url, '--fullscreen'], check=True)
                    saison_str = saison
                    if "vostfr" in url.lower():
                        version_str = "VOSTFR"
                    elif "/vf" in url.lower():
                        version_str = "VF"
                    else:
                        version_str = ""
                    if version_str and version_str.lower() not in saison_str.lower():
                        saison_str = f"{saison_str} - {version_str}"
                    add_to_history(
                        anime_name=anime_name,
                        episode=f"Episode {next_ep}",
                        saison=saison_str,
                        url=url,
                        debug=False
                    )
                except FileNotFoundError:
                    print("Erreur : mpv n'est pas installé.")
                except Exception as e:
                    print(f"Erreur lors de la lecture : {e}")

        def key_q(self):
            self.app.pop_screen()

        def key_d(self):
            self._delete_selected_entry()

        def key_delete(self):
            self._delete_selected_entry()

        def key_escape(self):
            self.key_q()

        def _delete_selected_entry(self):
            if not hasattr(self, "list_view") or not hasattr(self, "entries"):
                return
            idx = self.list_view.index
            if idx < 0 or idx >= len(self.entries):
                return
            entry_id = self.entries[idx][0]
            delete_history_entry(entry_id)
            del self.entries[idx]
            self.list_view.children[idx].remove()
            if not self.entries:
                self.list_view.visible = False
                self.mount(Label("Aucun historique trouvé.", id="history-empty"))

    class HistoryCheckFinalScreen(Screen):
        def compose(self) -> ComposeResult:
            yield Label("Historique (dernier épisode en rouge) :", id="history-title")
            self.entries = get_history_entries()
            if not self.entries:
                yield Label("Aucun historique trouvé.", id="history-empty")
                return
            items = []
            self.last_ep_indices = set()
            for i, entry in enumerate(self.entries, 1):
                anime_name, episode, saison, url = entry[1:5]
                import re
                match = re.search(r'(\d+)$', episode)
                if match:
                    current_ep = int(match.group(1))
                else:
                    current_ep = None
                filever = get_episode_list(url)
                if not filever:
                    is_last = False
                else:
                    episodes = AnimeDownloader().get_anime_episode(url, filever)
                    if not episodes:
                        is_last = False
                    else:
                        ep_keys = [int(e) for e in episodes.keys() if e.isdigit()]
                        if not ep_keys or current_ep is None:
                            is_last = False
                        else:
                            is_last = (current_ep == max(ep_keys))
                label = f"{anime_name} - {episode} - {saison}"
                if is_last:
                    items.append(ListItem(Label(f"[red]{label}[/red]", markup=True)))
                else:
                    items.append(ListItem(Label(label)))
            self.list_view = ListView(*items, id="history-list")
            yield self.list_view
            yield Label("Entrée: relire l'épisode suivant, d: supprimer, q: retour menu", id="history-help")

        def on_mount(self):
            if hasattr(self, "list_view"):
                self.list_view.index = 0
                self.set_focus(self.list_view)

        def key_q(self):
            self.app.pop_screen()
        def key_escape(self):
            self.key_q()
            
    class PlanningScreen(Screen):
        def compose(self) -> ComposeResult:
            yield Label("📅  Planning", id="planning-title")
            self.days, self.planning = self.get_planning()
            if not self.days:
                yield Label("Aucun planning trouve.", id="planning-empty")
                yield Label("[bold]q[/] retour", id="planning-help")
                return
            items = [ListItem(Label(f"  {day.strip()}")) for day in self.days]
            self.day_list = ListView(*items, id="planning-day-list")
            yield self.day_list
            self.anime_list = None
            yield Label("[bold]Entree[/] voir   [bold]q[/] retour", id="planning-help")

        def get_planning(self):
            url = f"https://{DOMAIN}/planning/"
            headers = {
                "user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:134.0) Gecko/20100101 Firefox/134.0",
                "accept-language": "en-US,en;q=0.5",
                "connection": "keep-alive"
            }
            try:
                response = requests.get(url, headers=headers)
                html_content = response.text
                day_pattern = r'<h2 class="titreJours[^>]*>([^<]+)</h2>'
                import re
                days = re.findall(day_pattern, html_content)
                planning = {day.strip(): [] for day in days}
                day_sections = re.split(day_pattern, html_content)
                for i in range(1, len(day_sections), 2):
                    current_day = day_sections[i].strip()
                    day_content = day_sections[i + 1]
                    if current_day in planning:
                        cards = re.findall(
                            r'<a href="(/catalogue/[^"]+)"[^>]*>.*?<h3[^>]*>([^<]+)</h3>',
                            day_content, re.DOTALL
                        )
                        if not cards:
                            cards = re.findall(
                                r'<a href="(/catalogue/[^"]+)"[^>]*>.*?<img[^>]*alt="([^"]*)"',
                                day_content, re.DOTALL
                            )
                        for card_url, card_title in cards:
                            planning[current_day].append((card_title.strip(), card_url.strip(), "", ""))
                days_list = list(planning.keys())
                return days_list, planning
            except Exception:
                return [], {}

        def on_mount(self):
            if hasattr(self, "day_list"):
                self.day_list.index = 0
                self.set_focus(self.day_list)

        def on_list_view_selected(self, event):
            if hasattr(self, "day_list") and event.control is self.day_list:
                idx = self.day_list.index
                if idx < 0 or idx >= len(self.days):
                    return
                selected_day = self.days[idx]
                animes = self.planning[selected_day]
                if self.anime_list:
                    self.anime_list.remove()
                if not animes:
                    self.anime_list = ListView(ListItem(Label("Aucun anime ce jour.")), id="anime-list")
                else:
                    items = [ListItem(Label(f"{title}")) for (title, url, time, version) in animes]
                    self.anime_list = ListView(*items, id="anime-list")
                self.mount(self.anime_list)
                self.set_focus(self.anime_list)
            elif hasattr(self, "anime_list") and event.control is self.anime_list:
                idx = self.anime_list.index
                day_idx = self.day_list.index
                if day_idx < 0 or day_idx >= len(self.days):
                    return
                selected_day = self.days[day_idx]
                animes = self.planning[selected_day]
                if idx < 0 or idx >= len(animes):
                    return
                title, url, time, version = animes[idx]
                season_url = f"https://{DOMAIN}{url}" if url.startswith('/') else f"https://{DOMAIN}/catalogue/{url}"
                saison_name = f"{time} - {version}" if time or version else version
                self.app.push_screen(EpisodesScreen(title, saison_name, season_url))

        def key_q(self):
            if hasattr(self, "anime_list") and self.anime_list in self.children:
                self.anime_list.remove()
                self.set_focus(self.day_list)
            else:
                self.app.pop_screen()

        def key_escape(self):
            self.key_q()

    class UpcomingScreen(Screen):
        def compose(self) -> ComposeResult:
            yield Label("🆕  Prochains episodes", id="upcoming-title")
            items = self.get_upcoming()
            if not items:
                yield Label("Aucun resultat trouve.", id="upcoming-empty")
            else:
                self.upcoming_list = ListView(*items, id="upcoming-list")
                yield self.upcoming_list
            yield Label("[bold]q[/] retour", id="upcoming-help")

        def get_upcoming(self):
            try:
                url = "https://animecountdown.com/upcoming"
                headers = HEADERS_BASE.copy()
                response = requests.get(url, headers=headers)
                soup = BeautifulSoup(response.text, 'html.parser')
                anime_list = soup.find_all('a', class_='countdown-content-trending-item')
                display_items = []
                for anime in anime_list:
                    anime_title = anime.find('countdown-content-trending-item-title').text.strip()
                    anime_episode = anime.find('countdown-content-trending-item-desc').text.strip()
                    display_items.append(ListItem(Label(f"{anime_title} - {anime_episode}")))
                return display_items
            except Exception:
                return []

        def on_mount(self):
            if hasattr(self, "upcoming_list"):
                self.upcoming_list.index = 0
                self.set_focus(self.upcoming_list)

        def key_q(self):
            self.app.pop_screen()
        def key_escape(self):
            self.key_q()

    class EpisodesScreen(Screen):
        def __init__(self, anime_name, season_name, season_url):
            super().__init__()
            self.anime_name = anime_name
            self.season_name = season_name
            self.season_url = season_url
            self.episodes = []
            self.episodes_dict = {}
            self.status_label = None
        def compose(self) -> ComposeResult:
            yield Label(f"🎬  {self.anime_name}", id="episodes-title")
            yield Label(f"  {self.season_name}", id="anime-version")
            self.episodes_dict = self.get_episodes()
            if not self.episodes_dict:
                yield Label("Aucun episode trouve.", id="episodes-empty")
            else:
                items = [ListItem(Label(f"  Episode {ep}")) for ep in self.episodes_dict.keys()]
                self.episode_list = ListView(*items, id="episode-list")
                yield self.episode_list
            self.status_label = Label("[bold]Entree[/] lancer   [bold]q[/] retour", id="episodes-help")
            yield self.status_label
        def get_episodes(self):
            filever = get_episode_list(self.season_url)
            if not filever:
                return {}
            return AnimeDownloader().get_anime_episode(self.season_url, filever)
        def on_mount(self):
            if hasattr(self, "episode_list"):
                self.episode_list.index = 0
                self.set_focus(self.episode_list)
        def on_list_view_selected(self, event):
            if hasattr(self, "episode_list") and event.control is self.episode_list:
                idx = self.episode_list.index
                ep_keys = list(self.episodes_dict.keys())
                if 0 <= idx < len(ep_keys):
                    ep = ep_keys[idx]
                    video_id = self.episodes_dict[ep]
                    self.status_label.update(f"[bold]Recuperation de l'episode {ep}...[/]")
                    video_url = AnimeDownloader().get_video_url(video_id)
                    if not video_url:
                        self.status_label.update("[red]Impossible de recuperer l'URL de la video.[/]")
                        return
                    if video_url.startswith('//'):
                        video_url = 'https:' + video_url
                    self.status_label.update(f"[bold]Lecture de l'episode {ep} avec mpv...[/]")
                    self.app.pop_screen()
                    try:
                        subprocess.run(['mpv', video_url, '--fullscreen'], check=True)
                        self.status_label.update("[green]Lecture terminee.[/]")
                        saison = self.season_name
                        if "vostfr" in self.season_url.lower():
                            version_str = "VOSTFR"
                        elif "/vf" in self.season_url.lower():
                            version_str = "VF"
                        else:
                            version_str = ""
                        if version_str and version_str.lower() not in saison.lower():
                            saison = f"{saison} - {version_str}"
                        add_to_history(
                            anime_name=self.anime_name,
                            episode=f"Episode {ep}",
                            saison=saison,
                            url=self.season_url,
                            debug=False
                        )
                    except FileNotFoundError:
                        self.status_label.update("[red]Erreur : mpv n'est pas installe.[/]")
                    except Exception as e:
                        self.status_label.update(f"[red]Erreur lors de la lecture : {e}[/]")
        def key_q(self):
            self.app.pop_screen()
        def key_escape(self):
            self.key_q()

    class VersionSelectScreen(Screen):
        def __init__(self, anime_name, anime_url, versions):
            super().__init__()
            self.anime_name = anime_name
            self.anime_url = anime_url
            self.versions = versions

        def compose(self) -> ComposeResult:
            yield Label(f"🎬  {self.anime_name}", id="episodes-title")
            yield Label("Choisis la version", id="version-title")
            items = [ListItem(Label(f"  {label}")) for label, url in self.versions]
            self.version_list = ListView(*items, id="version-list")
            yield self.version_list
            yield Label("[bold]Entree[/] valider   [bold]q[/] retour", id="version-help")

        def on_mount(self):
            self.version_list.index = 0
            self.set_focus(self.version_list)

        def on_list_view_selected(self, event):
            idx = self.version_list.index
            if 0 <= idx < len(self.versions):
                label, url = self.versions[idx]
                self.app.push_screen(AnimeInfoScreen(self.anime_name, url))
        def key_q(self):
            self.app.pop_screen()
        def key_escape(self):
            self.key_q()

    class AnimeInfoScreen(Screen):
        def __init__(self, anime_name, anime_url):
            super().__init__()
            self.anime_name = anime_name
            self.anime_url = anime_url
            self.seasons = []
        def compose(self) -> ComposeResult:
            try:
                response = requests.get(self.anime_url, headers={
                    "user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:134.0) Gecko/20100101 Firefox/134.0",
                    "accept-language": "en-US,en;q=0.5",
                    "connection": "keep-alive"
                })
                seasons = get_seasons(response.text)
            except Exception:
                seasons = []

            versions = {}
            for season in seasons:
                url = season['url'].lower()
                if 'vostfr' in url:
                    versions.setdefault('VOSTFR', []).append(season)
                elif 'vf' in url:
                    versions.setdefault('VF', []).append(season)
                else:
                    versions.setdefault('AUTRE', []).append(season)

            main_versions = [v for v in versions if v in ("VOSTFR", "VF")]
            if len(main_versions) > 1:
                version_choices = []
                for label in main_versions:
                    version_url = self.anime_url.rstrip('/') + '/' + versions[label][0]['url'].split('/')[0] + '/' + label.lower()
                    version_choices.append((label, version_url))
                self.app.push_screen(VersionSelectScreen(self.anime_name, self.anime_url, version_choices))
                return

            if len(versions) == 1:
                label = list(versions.keys())[0]
                yield Label(f"  Version : {label}", id="anime-version")

            yield Label(f"🎬  {self.anime_name}", id="anime-info-title")
            yield Label(f"  {self.anime_url}", id="anime-info-url")
            self.seasons = seasons
            if not self.seasons:
                yield Label("Aucune saison trouvee.", id="anime-info-noseason")
            else:
                items = [ListItem(Label(f"  {season['name']}")) for season in self.seasons]
                self.season_list = ListView(*items, id="season-list")
                yield self.season_list
                yield Label("[bold]Entree[/] choisir   [bold]q[/] retour", id="anime-info-help")
        def get_seasons(self):
            try:
                response = requests.get(self.anime_url, headers={
                    "user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:134.0) Gecko/20100101 Firefox/134.0",
                    "accept-language": "en-US,en;q=0.5",
                    "connection": "keep-alive"
                })
                return get_seasons(response.text)
            except Exception:
                return []
        def on_mount(self):
            if hasattr(self, "season_list"):
                self.season_list.index = 0
                self.set_focus(self.season_list)
        def on_list_view_selected(self, event):
            if hasattr(self, "season_list") and event.control is self.season_list:
                idx = self.season_list.index
                if 0 <= idx < len(self.seasons):
                    season = self.seasons[idx]
                    season_url = self.anime_url.rstrip('/') + '/' + season['url'].lstrip('/')
                    self.app.push_screen(EpisodesScreen(self.anime_name, season['name'], season_url))
        def key_q(self):
            self.app.pop_screen()
        def key_escape(self):
            self.key_q()

    class SearchScreen(Screen):
        def __init__(self, search_term=None):
            super().__init__()
            self.search_term = search_term
        def compose(self) -> ComposeResult:
            yield Label("🔍  Recherche", id="search-title")
            self.input = Input(placeholder="Tape le nom de l'anime...", id="search-input")
            yield self.input
            self.result_label = Label("", id="search-result")
            yield self.result_label
            self.results_list = None
            self.animes = []
            self.urls = []
            yield Label("[bold]Entree[/] valider   [bold]q[/] retour", id="search-help")
        def on_mount(self):
            self.set_focus(self.input)
            if self.search_term:
                self.input.value = self.search_term
                self.on_input_submitted(Input.Submitted(self.input, self.search_term))

        def on_input_submitted(self, event: Input.Submitted):
            query = event.value.strip()
            if not query:
                self.result_label.update("")
                if self.results_list:
                    self.results_list.remove()
                    self.results_list = None
                self.animes = []
                self.urls = []
                return
            self.result_label.update(f"[bold]Recherche de \"{query}\"...[/]")
            animes, urls = AnimeDownloader().get_catalogue(query)
            if self.results_list:
                self.results_list.remove()
                self.results_list = None
            self.animes = animes
            self.urls = urls
            if not animes:
                self.result_label.update("[red]Aucun anime trouve.[/]")
                return
            items = [ListItem(Label(f"  {anime}")) for anime in animes]
            self.results_list = ListView(*items, id="search-results-list")
            self.mount(self.results_list)
            self.set_focus(self.results_list)
            self.result_label.update(f"[green]{len(animes)} resultat(s) trouve(s)[/]")

        def on_list_view_selected(self, event):
            if self.results_list and event.control is self.results_list:
                idx = self.results_list.index
                if 0 <= idx < len(self.animes):
                    anime_name = self.animes[idx]
                    anime_url = self.urls[idx]
                    self.app.push_screen(AnimeInfoScreen(anime_name, anime_url))

        def key_q(self):
            self.app.pop_screen()
        def key_escape(self):
            self.key_q()

    class AnimeSamaTUI(App):
        CSS_PATH = "anime-sama.tcss"
        TITLE = "Anime-sama"
        SUB_TITLE = "Terminal anime viewer"
        BINDINGS = [
            ("q", "quit", "Quitter"),
        ]

        def __init__(self, start_screen=None, search_term=None, pre_screen=None):
            super().__init__()
            self.start_screen = start_screen
            self.search_term = search_term
            self.pre_screen = pre_screen

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            self.menu_label = Label("", id="title")
            yield self.menu_label
            yield Container(
                MainMenu(),
                id="main-container"
            )
            yield Footer()

        def on_mount_screen(self, event=None):
            if hasattr(self, "menu_label"):
                dot_color = "green" if IS_DOMAIN_AVAILABLE else "red"
                status_text = "dispo" if IS_DOMAIN_AVAILABLE else "indisponible"
                self.menu_label.update(f"[{dot_color}]● {DOMAIN} ({status_text})[/]")

        async def on_mount(self):
            self.on_mount_screen()
            if self.pre_screen:
                await self.push_screen(self.pre_screen)
            elif self.search_term:
                await self.push_screen(SearchScreen(search_term=self.search_term))
            elif self.start_screen == "planning":
                await self.push_screen(PlanningScreen())
            elif self.start_screen == "history":
                await self.push_screen(HistoryScreen())
            else:
                self.set_focus(self.query_one("#menu-list"))

        async def handle_menu_select(self, event: MenuSelect):
            action = MENU_ITEMS[event.index][1]
            if action == "search":
                await self.action_search()
            elif action == "history":
                await self.action_history()
            elif action == "planning":
                await self.action_planning()
            elif action == "upcoming":
                await self.action_upcoming()

        async def action_search(self):
            await self.push_screen(SearchScreen())
        async def action_history(self):
            await self.push_screen(HistoryScreen())
        async def action_planning(self):
            await self.push_screen(PlanningScreen())
        async def action_upcoming(self):
            await self.push_screen(UpcomingScreen())

        def on_menu_select(self, event: MenuSelect):
            asyncio.create_task(self.handle_menu_select(event))

    def tui_main(args):
        start_screen = None
        if args.planing:
            start_screen = "planning"
        elif args.continuer:
            start_screen = "history"

        if args.check_final:
            app = AnimeSamaTUI(pre_screen=HistoryCheckFinalScreen())
            app.run()
        else:
            search_term = " ".join(args.query) if args.query else None
            app = AnimeSamaTUI(start_screen=start_screen, search_term=search_term)
            app.run()

def main():
    parser = argparse.ArgumentParser(
        description=f"Anime-sama CLI - Interface CLI et TUI pour {DOMAIN}",
        add_help=False
    )
    parser.add_argument("query", nargs="*", help="Recherche d'anime")
    parser.add_argument("-c", "--continuer", action="store_true", help="Afficher l'historique")
    parser.add_argument("-f", "--full", action="store_true", help="Vérification des derniers épisodes dans l'historique")
    parser.add_argument("--vf", action="store_true", help="Recherche uniquement en VF")
    parser.add_argument("--debug", action="store_true", help="Mode debug")
    parser.add_argument("-h", "--help", action="store_true", help="Afficher l'aide")
    parser.add_argument("-p", "--planing", action="store_true", help="Afficher le planning")
    parser.add_argument("-up", "--upcoming", action="store_true", help="Afficher les prochains épisodes à sortir")
    parser.add_argument("-t", "--textual", action="store_true", help="Utiliser l'interface TUI (Textual)")
    parser.add_argument("--cli", action="store_true", help="Utiliser l'interface en ligne de commande traditionnelle")
    parser.add_argument("-cf", "--check-final", action="store_true", help="Historique avec vérification du dernier épisode")
    
    args = parser.parse_args()
    
    if args.help:
        display_help()
        return
    
    use_tui = not args.cli and TEXTUAL_AVAILABLE
    
    if args.textual and not TEXTUAL_AVAILABLE:
        print("Erreur: La librairie Textual n'est pas installée. Impossible d'utiliser le mode TUI.")
        print("Installez-la avec: pip install textual")
        print("Passage en mode CLI...")
        use_tui = False
    
    if use_tui:
        tui_main(args)
    else:
        try:
            cli_main(args)
        except KeyboardInterrupt:
            print("\nProgramme interrompu par l'utilisateur")
        except Exception as e:
            print(f"\nUne erreur s'est produite : {str(e)}")

if __name__ == "__main__":
    main()
