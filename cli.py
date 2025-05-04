import requests
import subprocess
import re
import sys
import json
import sqlite3
from bs4 import BeautifulSoup
import os
import time
from datetime import datetime
import locale
import pathlib
import argparse

HEADERS_BASE = {
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:134.0) Gecko/20100101 Firefox/134.0",
    "accept-language": "en-US,en;q=0.5",
    "connection": "keep-alive"
}

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
            sibnet_links = {}
            matches = re.finditer(r'https://video\.sibnet\.ru/shell\.php\?videoid=(\d+)', content)
            sibnet_links = {str(i): match.group(1) for i, match in enumerate(matches, 1)}
            return sibnet_links
        except requests.RequestException as e:
            print(f"Erreur lors de la récupération des épisodes : {e}")
            return {}

    def get_video_url(self, video_id):
        try:
            url = f"https://video.sibnet.ru/shell.php"
            print(f"Tentative de récupération de la vidéo {video_id}...")
            response = self.session.get(url, params={"videoid": video_id})
            response.raise_for_status()
            html_content = response.text
            print("Recherche du pattern dans le contenu HTML...")
            match = re.search(r'player\.src\(\[\{src: "/v/([^/]+)/', html_content)
            if match:
                video_hash = match.group(1)
                url_sibnet = f"https://video.sibnet.ru/v/{video_hash}/{video_id}.mp4"
                print(f"URL construite : {url_sibnet}")
                headers_sibnet = {
                    **HEADERS_BASE,
                    "range": "bytes=0-",
                    "accept-encoding": "identity",
                    "referer": "https://video.sibnet.ru/",
                }
                response_sibnet = self.session.get(url_sibnet, headers=headers_sibnet, allow_redirects=False)
                if response_sibnet.status_code == 302:
                    return response_sibnet.headers['Location']
                else:
                    print(f"Status code inattendu : {response_sibnet.status_code}")
            else:
                print("Pattern non trouvé dans le HTML")
            return None
        except requests.RequestException as e:
            print(f"Erreur lors de la récupération de l'URL vidéo : {e}")
            return None

    def get_catalogue(self, query="", vf=False): 
        try:
            url = "https://anime-sama.fr/catalogue/"
            headers = {
                "host": "anime-sama.fr",
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
                "referer": "https://anime-sama.fr/catalogue/",
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
            for card in soup.find_all('a', href=True):
                titre = None
                titre_tag = card.find('h1', class_='text-white font-bold uppercase text-md line-clamp-2')
                if titre_tag:
                    titre = titre_tag.text.strip()
                if titre and 'catalogue' in card['href']:
                    animes.append(titre)
                    urls.append(card['href'])
            if vf:
                urls = [link.replace("vostfr", "vf") for link in urls]
            self.debug_print(f"Nombre de titres trouvés: {len(animes)}")
            self.debug_print(f"Titres trouvés: {animes}")
            return animes, urls
        except requests.RequestException as e:
            print(f"Erreur lors de la récupération du catalogue : {e}")
            self.debug_print(f"Exception complète: {str(e)}")
            return [], []

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
        "host": "anime-sama.fr",
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
        if match:
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
    url = "https://anime-sama.fr/planning/"
    headers = HEADERS_BASE.copy()
    response = requests.get(url, headers=headers)
    html_content = response.text
    day_pattern = r'<h2 class="titreJours[^>]*>([^<]+)</h2>'
    anime_pattern = r'cartePlanningAnime\("([^"]+)", "([^"]+)", "[^"]+", "([^"]+)", "[^"]*", "([^"]+)"\);'
    days = re.findall(day_pattern, html_content)
    planning = {day.strip(): [] for day in days}
    day_sections = re.split(day_pattern, html_content)
    for i in range(1, len(day_sections), 2):
        current_day = day_sections[i].strip()
        day_content = day_sections[i + 1]
        if current_day in planning:
            matches = re.findall(anime_pattern, day_content)
            for match in matches:
                title, url, time, version = match
                planning[current_day].append((title, url, time, version))
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
        print(f"{i}. {title} - {time} - {version}")
    print("0. Retour")
    choix = input("Numéro de l'anime : ").strip()
    if choix == "0":
        return
    if not choix.isdigit() or int(choix) < 1 or int(choix) > len(animes):
        print("Numéro invalide.")
        return
    selected_anime = animes[int(choix)-1]
    anime_url = f"https://anime-sama.fr/catalogue/{selected_anime[1]}"
    print(f"URL de la saison : {anime_url}")
    afficher_episodes_saison(anime_url, selected_anime[0], selected_anime[3])

def display_upcoming():
    print("\n--- Prochains épisodes à sortir (texte) ---")
    url = "https://animecountdown.com/upcoming"
    headers = HEADERS_BASE.copy()
    response = requests.get(url, headers=headers)
    html_content = response.text
    from bs4 import BeautifulSoup
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

Information:
    L'historique est stocké localement dans ~/.local/share/animesama-cli/history.db

Examples:
    anime                  # Lance le menu principal
    anime naruto           # Recherche directement "naruto"
    anime -c               # Affiche l'historique simple
    anime -cf              # Affiche l'historique avec vérification des derniers épisodes
    anime --vf naruto      # Recherche "naruto" uniquement en VF
    anime --debug naruto   # Recherche "naruto" avec le mode debug
    anime -p               # Affiche le planning des animes par jour
    anime -up              # Affiche les prochains épisodes à sortir
    """
    print(help_text)

def main(args_from_history=None):
    parser = argparse.ArgumentParser(
        description="Anime-sama CLI (inspiré de ani-cli)",
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
    if args_from_history:
        args = parser.parse_args(args_from_history)
    else:
        args = parser.parse_args()
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

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProgramme interrompu par l'utilisateur")
    except Exception as e:
        print(f"\nUne erreur s'est produite : {str(e)}")