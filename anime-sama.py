import requests
import subprocess
import re
import sys
import json
import sqlite3
from bs4 import BeautifulSoup
import curses
from curses import wrapper
import os
import time
from datetime import datetime
import locale
import pathlib

HEADERS_BASE = {
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:134.0) Gecko/20100101 Firefox/134.0",
    "accept-language": "en-US,en;q=0.5",
    "connection": "keep-alive"
}

# Define the database path
def get_db_path():
    db_dir = os.path.expanduser("~/.local/share/animesama-cli")
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, "history.db")

# Function to initialize the database
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

# Function to add entry to history
def add_to_history(anime_name, episode, saison, url, debug=False):
    try:
        # Initialize database if it doesn't exist
        init_db()
        
        # Connect to database
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        
        # Check if entry already exists
        cursor.execute(
            "SELECT id FROM history WHERE anime_name = ? AND saison = ?", 
            (anime_name, saison)
        )
        existing_entry = cursor.fetchone()
        
        if existing_entry:
            # Update existing entry
            cursor.execute(
                "UPDATE history SET episode = ?, timestamp = CURRENT_TIMESTAMP WHERE id = ?",
                (episode, existing_entry[0])
            )
            if debug:
                print("[DEBUG] Historique mis à jour avec succès")
            else:
                print("✓ Historique mis à jour avec succès")
        else:
            # Insert new entry
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
            querystring = {"search": query}
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
            titles = soup.find_all('h1', class_='text-white font-bold uppercase text-md line-clamp-2')
            links = [a['href'] for a in soup.find_all('a', href=True) if 'catalogue' in a['href']]
            
            if vf:
                links = [link.replace("vostfr", "vf") for link in links]
            
            self.debug_print(f"Nombre de titres trouvés: {len(titles)}")
            self.debug_print(f"Titres trouvés: {[title.text.strip() for title in titles]}")
            
            return [title.text.strip() for title in titles], links
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
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:134.0) Gecko/20100101 Firefox/134.0",
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

def display_menu(stdscr, items, urls=None, delete_callback=None):
    curses.curs_set(0)
    curses.use_default_colors()
    stdscr.clear()
    current_row = 0
    scroll_offset = 0
    
    curses.start_color()
    curses.init_pair(1, curses.COLOR_RED, -1) 
    curses.init_pair(2, curses.COLOR_BLUE, -1)
    curses.init_pair(3, curses.COLOR_GREEN, -1)
    curses.init_pair(4, curses.COLOR_YELLOW, -1)  # Added yellow color for titles

    max_height, max_width = stdscr.getmaxyx()
    max_display = max_height - 2
    margin_top = 2
    
    # Add a title and border
    title = "Anime-Sama Viewer"
    stdscr.addstr(0, max_width//2 - len(title)//2, title, curses.A_BOLD | curses.color_pair(4))
    
    while True:
        stdscr.clear()
        
        # Add a title and border
        stdscr.addstr(0, max_width//2 - len(title)//2, title, curses.A_BOLD | curses.color_pair(4))
        stdscr.hline(1, 0, curses.ACS_HLINE, max_width)
        
        position_text = f"[{current_row + 1}/{len(items)}]"
        stdscr.addstr(max_height-1, 0, position_text)
        
        # Add navigation help
        help_text = "↑/↓: Navigate | Enter: Select | i: Info | Del: Delete"
        if len(help_text) < max_width:
            stdscr.addstr(max_height-1, max_width - len(help_text) - 1, help_text)
        
        start_idx = scroll_offset
        end_idx = min(len(items), scroll_offset + max_display)
        
        for idx, item in enumerate(items[start_idx:end_idx], start=start_idx):
            x = max_width//2 - len(item)//2
            y = (idx - scroll_offset) + margin_top
            
            if "Dernier Episode" in item:
                stdscr.attron(curses.color_pair(1))
            
            if idx == current_row:
                stdscr.attron(curses.A_REVERSE)
                stdscr.addstr(y, x, item[:max_width-1])
                stdscr.attroff(curses.A_REVERSE)
            else:
                stdscr.addstr(y, x, item[:max_width-1])
            
            if "Dernier Episode" in item:
                stdscr.attroff(curses.color_pair(1))
            
            if urls:
                if "vostfr" in urls[idx].lower():
                    stdscr.attron(curses.color_pair(2))
                    stdscr.addstr(y, x + item.lower().find("vostfr"), "VOSTFR")
                    stdscr.attroff(curses.color_pair(2))
                elif "vf" in urls[idx].lower():
                    stdscr.attron(curses.color_pair(3))
                    stdscr.addstr(y, x + item.lower().find("vf"), "VF")
                    stdscr.attroff(curses.color_pair(3))
        
        if scroll_offset > 0:
            stdscr.addstr(margin_top-1, max_width-3, "↑")
        if end_idx < len(items):
            stdscr.addstr(max_height-1, max_width-3, "↓")
                
        key = stdscr.getch()
        
        if key == curses.KEY_UP:
            if current_row > 0:
                current_row -= 1
                if current_row < scroll_offset:
                    scroll_offset = current_row
        elif key == curses.KEY_DOWN:
            if current_row < len(items)-1:
                current_row += 1
                if current_row >= scroll_offset + max_display:
                    scroll_offset = current_row - max_display + 1
        elif key == curses.KEY_PPAGE:
            current_row = max(0, current_row - max_display)
            scroll_offset = max(0, scroll_offset - max_display)
        elif key == curses.KEY_NPAGE:
            current_row = min(len(items)-1, current_row + max_display)
            scroll_offset = min(len(items) - max_display, scroll_offset + max_display)
        elif key == curses.KEY_HOME:
            current_row = 0
            scroll_offset = 0
        elif key == curses.KEY_END:
            current_row = len(items) - 1
            scroll_offset = max(0, len(items) - max_display)
        elif key == curses.KEY_ENTER or key in [10, 13]:
            return current_row
        elif key == ord('i') and urls:
            stdscr.clear()
            stdscr.addstr(0, 0, f"Informations sur l'anime: {items[current_row]}", curses.A_BOLD | curses.color_pair(4))
            stdscr.hline(1, 0, curses.ACS_HLINE, max_width)
            
            try:
                response = requests.get(urls[current_row], headers=HEADERS_BASE)
                response.raise_for_status()
                page_content = response.text
                
                lines = [page_content[i:i+max_width] for i in range(0, len(page_content), max_width)]
                
                for idx, line in enumerate(lines, start=2):
                    if idx < max_height - 1:
                        stdscr.addstr(idx, 0, line)
                
                stdscr.addstr(max_height - 1, 0, "Appuyez sur n'importe quelle touche pour revenir.")
            except requests.RequestException as e:
                stdscr.addstr(2, 0, f"Erreur lors de la récupération de la page: {e}")
            
            stdscr.refresh()
            stdscr.getch()
        elif key in [curses.KEY_BACKSPACE, 127, curses.KEY_DC]:
            if delete_callback:
                delete_callback(current_row)
                items.pop(current_row)
                if current_row >= len(items):
                    current_row = len(items) - 1
                if scroll_offset > current_row:
                    scroll_offset = current_row

        stdscr.refresh()

def debug_print(message, debug_mode=False):
    if debug_mode:
        print(f"[DEBUG] {message}")

def display_history(stdscr, full_check=False):
    def delete_history_entry(index):
        try:
            # Connect to database
            conn = sqlite3.connect(get_db_path())
            cursor = conn.cursor()
            
            # Get all history entries
            cursor.execute("SELECT id FROM history ORDER BY timestamp DESC")
            entries = cursor.fetchall()
            
            if entries and 0 <= index < len(entries):
                entry_id = entries[index][0]
                
                # Delete the entry
                cursor.execute("DELETE FROM history WHERE id = ?", (entry_id,))
                conn.commit()
                conn.close()
                
                curses.endwin()
                print("✓ Entrée supprimée de l'historique")
                time.sleep(1)  # Give user time to see the message
            else:
                curses.endwin()
                print("✗ Erreur lors de la suppression de l'entrée: Entrée non trouvée")
                time.sleep(1)
        except Exception as e:
            curses.endwin()
            print(f"✗ Erreur lors de la suppression de l'entrée de l'historique: {e}")
            time.sleep(1)

    try:
        # Initialize database if it doesn't exist
        init_db()
        
        # Connect to database
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        
        # Get all history entries sorted by most recent
        cursor.execute(
            "SELECT id, anime_name, episode, saison, url FROM history ORDER BY timestamp DESC"
        )
        history_entries = cursor.fetchall()
        conn.close()
        
        if not history_entries:
            curses.endwin()
            print("ℹ Aucun historique trouvé")
            return
        
        formatted_entries = []
        urls = []
        
        downloader = AnimeDownloader(debug=False)
        
        # Show loading message
        max_height, max_width = stdscr.getmaxyx()
        stdscr.clear()
        loading_msg = "Chargement de l'historique..."
        stdscr.addstr(max_height//2, max_width//2 - len(loading_msg)//2, loading_msg)
        stdscr.refresh()
        
        for entry in history_entries:
            entry_id, anime_name, episode, saison, url = entry
            
            version = ""
            if "vostfr" in url.lower():
                version = "VOSTFR"
            elif "vf" in url.lower():
                version = "VF"
            
            if full_check:
                current_episode = int(episode.split()[1])
                filever = get_episode_list(url)
                
                if filever:
                    episodes = downloader.get_anime_episode(url, filever)
                    if episodes:
                        max_episode = max(int(ep_num) for ep_num in episodes.keys())
                        if current_episode >= max_episode:
                            formatted_entry = f"{anime_name} - Episode {max_episode} - {saison} - Dernier Episode {version}"
                        else:
                            formatted_entry = f"{anime_name} - {episode} - {saison} {version}"
                    else:
                        formatted_entry = f"{anime_name} - {episode} - {saison} {version}"
                else:
                    formatted_entry = f"{anime_name} - {episode} - {saison} {version}"
            else:
                formatted_entry = f"{anime_name} - {episode} - {saison} {version}"
            
            formatted_entries.append(formatted_entry)
            urls.append(url)
        
        selected_idx = display_menu(stdscr, formatted_entries, urls, delete_callback=delete_history_entry)
        
        if selected_idx is not None:
            selected_url = urls[selected_idx]
            curses.endwin()
            
            downloader = AnimeDownloader(debug=False)
            
            # Show loading message
            print("⏳ Chargement des épisodes...")
            
            filever = get_episode_list(selected_url)
            if filever:
                episodes = downloader.get_anime_episode(selected_url, filever)
                
                if episodes:
                    entry = history_entries[selected_idx]
                    entry_id, anime_name, episode_info, saison, url = entry
                    episode_num = int(episode_info.split()[1])
                    next_episode_num = episode_num + 1
                    next_episode_str = f"Episode {next_episode_num}"
                    
                    if str(next_episode_num) in episodes:
                        video_id = episodes[str(next_episode_num)]
                        
                        print(f"⏳ Récupération de l'épisode {next_episode_num}...")
                        video_url = downloader.get_video_url(video_id)
                        
                        if video_url:
                            if video_url.startswith('//'):
                                video_url = 'https:' + video_url
                            
                            print(f"▶️ Lancement de la lecture...")
                            try:
                                subprocess.run(['mpv', video_url, '--fullscreen'], check=True)
                                add_to_history(
                                    anime_name=anime_name,
                                    episode=next_episode_str,
                                    saison=saison,
                                    url=selected_url,
                                    debug=False
                                )
                            except subprocess.CalledProcessError as e:
                                print(f"✗ Erreur lors du lancement de MPV: {e}")
                            except FileNotFoundError:
                                print("✗ Erreur: MPV n'est pas installé sur votre système")
                        else:
                            print("✗ Impossible de récupérer l'URL de la vidéo")
                    else:
                        print(f"ℹ {anime_name} - {episode_info} - {saison} - Dernier Episode")
                else:
                    print("ℹ Aucun épisode trouvé")
            else:
                print("✗ Impossible de récupérer la liste des épisodes")
            
    except Exception as e:
        curses.endwin()
        print(f"✗ Erreur lors de la lecture de l'historique: {e}")

# Function to migrate database schema
def migrate_history_table():
    db_path = get_db_path()
    
    # Check if the database file exists
    if not os.path.exists(db_path):
        # Create new database with current schema
        init_db()
        return
    
    # Connect to existing database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if the table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='history'")
    table_exists = cursor.fetchone()
    
    if not table_exists:
        # If table doesn't exist, create it
        cursor.execute('''
        CREATE TABLE history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anime_name TEXT NOT NULL,
            episode TEXT NOT NULL,
            saison TEXT NOT NULL,
            url TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
    else:
        # Check if timestamp column exists
        cursor.execute("PRAGMA table_info(history)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]
        
        # Add timestamp column if it doesn't exist
        if 'timestamp' not in column_names:
            cursor.execute("ALTER TABLE history ADD COLUMN timestamp DATETIME DEFAULT CURRENT_TIMESTAMP")
    
    conn.commit()
    conn.close()

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

def afficher_planning(stdscr):
    import requests
    import re

    downloader = AnimeDownloader(debug=False)

    url = "https://anime-sama.fr/planning/"
    headers = {
        "host": "anime-sama.fr",
        "connection": "keep-alive",
        "upgrade-insecure-requests": "1",
        "user-agent": HEADERS_BASE["user-agent"],
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "sec-fetch-site": "same-origin",
        "sec-fetch-mode": "navigate",
        "sec-fetch-user": "?1",
        "sec-fetch-dest": "document",
        "sec-ch-ua": "\"Not A(Brand\";v=\"8\", \"Chromium\";v=\"132\", \"Google Chrome\";v=\"132\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "referer": "https://anime-sama.fr/planning/",
        "accept-language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7"
    }

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
            matches = re.findall(anime_pattern, day_content)
            for match in matches:
                title, url, time, version = match
                planning[current_day].append((title, url, time, version))

    stdscr.clear()
    stdscr.addstr("Sélectionnez un jour pour voir les animes:\n")
    days_list = list(planning.keys())
    selected_day_idx = display_menu(stdscr, days_list)

    stdscr.clear()
    selected_day = days_list[selected_day_idx]
    stdscr.addstr(f"Animes pour {selected_day}:\n")
    if planning[selected_day]:
        anime_options = [f"{title} - {time} - {version}" for title, _, time, version in planning[selected_day]]
        selected_anime_idx = display_menu(stdscr, anime_options)

        selected_anime = planning[selected_day][selected_anime_idx]
        anime_url = selected_anime[1]

        stdscr.clear()
        stdscr.addstr(f"Épisodes pour {selected_anime[0]}:\n")
        fetch_and_display_episodes(stdscr, anime_url)
    else:
        stdscr.addstr("  Aucun anime prévu pour ce jour.\n")
    stdscr.refresh()

def fetch_and_display_episodes(stdscr, anime_url):
    import requests
    import re
    import subprocess

    full_url = f"https://anime-sama.fr/catalogue/{anime_url}"
    stdscr.addstr(f"Fetching episodes from: {full_url}\n")
    stdscr.refresh()

    downloader = AnimeDownloader(debug=False)

    filever = get_episode_list(full_url)
    if filever:
        episodes = downloader.get_anime_episode(full_url, filever)
        if episodes:
            episode_list = [f"Episode {num}" for num in episodes.keys()]
            selected_episode_idx = display_menu(stdscr, episode_list)

            episode_num = list(episodes.keys())[selected_episode_idx]
            video_id = episodes[episode_num]

            video_url = downloader.get_video_url(video_id)
            if video_url:
                if video_url.startswith('//'):
                    video_url = 'https:' + video_url

                curses.endwin()

                try:
                    subprocess.run(['mpv', video_url, '--fullscreen'], check=True)

                    anime_name = anime_url.split('/')[0].replace('-', ' ').title()
                    saison = anime_url.split('/')[1].replace('saison', 'Saison ').capitalize()
                    add_to_history(
                        anime_name=anime_name,
                        episode=f"Episode {episode_num}",
                        saison=saison,
                        url=full_url,
                        debug=False
                    )
                except subprocess.CalledProcessError as e:
                    print(f"Erreur lors du lancement de MPV: {e}")
                except FileNotFoundError:
                    print("Erreur: MPV n'est pas installé sur votre système")
            else:
                stdscr.addstr("Impossible de récupérer l'URL de la vidéo\n")
        else:
            stdscr.addstr("Aucun épisode trouvé.\n")
    else:
        stdscr.addstr("Impossible de récupérer la liste des épisodes.\n")

    stdscr.refresh()
    stdscr.getch()

def extract_anime_url(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    link_tag = soup.find('a', href=True, class_='flex divide-x')
    if link_tag:
        return link_tag['href']
    return None

def display_upcoming(stdscr):
    url = "https://animecountdown.com/upcoming"
    headers = {
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "accept-language": "en-US,en;q=0.5",
        "upgrade-insecure-requests": "1",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "priority": "u=0, i",
        "te": "trailers"
    }

    try:
        # Initialiser les couleurs de manière plus sûre
        curses.start_color()
        if curses.has_colors():
            try:
                curses.init_pair(1, curses.COLOR_RED, 0)
                curses.init_pair(2, curses.COLOR_BLUE, 0)
                curses.init_pair(3, curses.COLOR_GREEN, 0)
                curses.init_pair(4, curses.COLOR_YELLOW, 0)
            except curses.error:
                pass

        response = requests.get(url, headers=headers)
        html_content = response.text
        soup = BeautifulSoup(html_content, 'html.parser')
        anime_list = soup.find_all('a', class_='countdown-content-trending-item')

        # Préparer la liste des animes à afficher avec leurs types
        display_items = []
        last_timestamp = None
        ONE_WEEK = 7 * 24 * 60 * 60  # Une semaine en secondes

        for anime in anime_list:
            anime_title = anime.find('countdown-content-trending-item-title').text.strip()
            anime_episode = anime.find('countdown-content-trending-item-desc').text.strip()
            anime_timestamp = int(anime.find('countdown-content-trending-item-countdown')['data-time']) + int(time.time())
            
            # Ajouter un séparateur si plus d'une semaine s'est écoulée
            if last_timestamp is not None:
                time_diff = anime_timestamp - last_timestamp
                if time_diff > ONE_WEEK:
                    display_items.append(("─" * 50, 4))  # Ligne de séparation en jaune
            
            last_timestamp = anime_timestamp
            
            date_format = datetime.fromtimestamp(anime_timestamp).strftime('%d/%m/%Y %H:%M')
            display_item = f"{anime_title} - {anime_episode} - {date_format}"
            
            # Déterminer le type pour la coloration
            if "movie" in anime_episode.lower():
                display_items.append((display_item, 1))  # Rouge
            elif "ova" in anime_episode.lower():
                display_items.append((display_item, 2))  # Bleu
            else:
                display_items.append((display_item, 3))  # Vert

        def display_upcoming_menu(stdscr, items):
            curses.curs_set(0)
            current_row = 0
            scroll_offset = 0
            
            max_height, max_width = stdscr.getmaxyx()
            max_display = max_height - 2
            margin_top = 2
            
            while True:
                stdscr.clear()
                position_text = f"[{current_row + 1}/{len(items)}]"
                stdscr.addstr(0, 0, position_text)
                
                start_idx = scroll_offset
                end_idx = min(len(items), scroll_offset + max_display)
                
                for idx, (item, color_pair) in enumerate(items[start_idx:end_idx], start=start_idx):
                    x = max_width//2 - len(item)//2
                    y = (idx - scroll_offset) + margin_top
                    
                    if idx == current_row and "─" not in item:  # Ne pas mettre en surbrillance les séparateurs
                        stdscr.attron(curses.A_REVERSE)
                    
                    try:
                        if curses.has_colors():
                            stdscr.attron(curses.color_pair(color_pair))
                        stdscr.addstr(y, x, item[:max_width-1])
                        if curses.has_colors():
                            stdscr.attroff(curses.color_pair(color_pair))
                    except curses.error:
                        stdscr.addstr(y, x, item[:max_width-1])
                    
                    if idx == current_row and "─" not in item:
                        stdscr.attroff(curses.A_REVERSE)
                
                if scroll_offset > 0:
                    stdscr.addstr(margin_top-1, max_width-3, "↑")
                if end_idx < len(items):
                    stdscr.addstr(max_height-1, max_width-3, "↓")
                
                key = stdscr.getch()
                
                if key == curses.KEY_UP:
                    # Trouver le prochain élément non-séparateur vers le haut
                    new_row = current_row - 1
                    while new_row >= 0 and "─" in items[new_row][0]:
                        new_row -= 1
                    if new_row >= 0:
                        current_row = new_row
                        if current_row < scroll_offset:
                            scroll_offset = current_row
                elif key == curses.KEY_DOWN:
                    # Trouver le prochain élément non-séparateur vers le bas
                    new_row = current_row + 1
                    while new_row < len(items) and "─" in items[new_row][0]:
                        new_row += 1
                    if new_row < len(items):
                        current_row = new_row
                        if current_row >= scroll_offset + max_display:
                            scroll_offset = current_row - max_display + 1
                elif key == curses.KEY_ENTER or key in [10, 13]:
                    if "─" not in items[current_row][0]:  # Ne pas sélectionner les séparateurs
                        return current_row
                
                stdscr.refresh()

        # Afficher le menu avec les animes à venir
        stdscr.clear()
        selected_idx = display_upcoming_menu(stdscr, display_items)
        
    except Exception as e:
        stdscr.clear()
        stdscr.addstr(0, 0, f"Erreur lors de la récupération des animes à venir: {str(e)}")
        stdscr.refresh()
        stdscr.getch()

def main(stdscr):
    try:
        debug_mode = "--debug" in sys.argv
        vf_mode = "--vf" in sys.argv
        if debug_mode:
            sys.argv.remove("--debug")
        if vf_mode:
            sys.argv.remove("--vf")
        
        downloader = AnimeDownloader(debug=debug_mode)
        
        try:
            curses.endwin()
            
            if len(sys.argv) == 1:
                menu_options = ["🔍 Recherche", "📜 Historique", "📅 Planning", "🔜 À venir"]
                stdscr.clear()
                selected_option = display_menu(stdscr, menu_options)
                curses.endwin()
                
                if selected_option == 0:
                    query = input("Entrez le nom de l'anime que vous recherchez : ")
                elif selected_option == 1:
                    display_history(stdscr)
                    return
                elif selected_option == 2:
                    afficher_planning(stdscr)
                    return
                elif selected_option == 3:
                    display_upcoming(stdscr)
                    return
            else:
                query = " ".join(sys.argv[1:])
            
            if not query.strip():
                return
            
            if debug_mode:
                print(f"[DEBUG] Recherche de : {query}")
            else:
                print(f"🔍 Recherche de : {query}")
                
            animes, urls = downloader.get_catalogue(query, vf=vf_mode)
            
            if not animes:
                print("ℹ Aucun anime trouvé")
                return
                
            try:
                curses.endwin()
            except:
                pass
            
            try:
                stdscr.clear()
                stdscr.refresh()
                
                selected_anime = display_menu(stdscr, animes, urls)
                
                curses.endwin()
            except Exception as e:
                if debug_mode:
                    print(f"[DEBUG] Erreur: {e}")
                return
            
            base_url = "https://anime-sama.fr/catalogue/"
            anime_url = base_url + animes[selected_anime].lower().replace(' !', '').replace(' ', '-').replace('Re:', 're-').replace(',', '').replace(':', '-').replace('--', '-') + "/"
            if vf_mode:
                anime_url = anime_url.replace("vostfr", "vf")
            if debug_mode:
                print(f"[DEBUG] URL de l'anime: {anime_url}")
            else:
                print(f"⏳ Chargement des saisons...")

            try:
                response = requests.get(anime_url, headers=HEADERS_BASE)
                
                if response.status_code != 200:
                    if debug_mode:
                        print(f"[DEBUG] Erreur HTTP: {response.status_code}")
                    return
                
                seasons = get_seasons(response.text)
                
                if not seasons:
                    if debug_mode:
                        print("[DEBUG] Aucune saison trouvée")
                    else:
                        print("ℹ Aucune saison trouvée")
                    return
                
                season_names = [season['name'] for season in seasons]
                
                try:
                    stdscr.clear()
                    stdscr.refresh()
                    
                    selected_season_idx = display_menu(stdscr, season_names)
                    selected_season = seasons[selected_season_idx]
                    
                    curses.endwin()
                    
                    season_url = anime_url + selected_season['url']
                    if vf_mode:
                        season_url = season_url.replace("vostfr", "vf")
                    
                    if debug_mode:
                        print(f"[DEBUG] URL de la saison: {season_url}")
                    else:
                        print(f"⏳ Chargement des épisodes...")
                        
                    filever = get_episode_list(season_url)
                    if filever:
                        episodes = downloader.get_anime_episode(season_url, filever)
                        
                        if episodes:
                            stdscr.clear()
                            stdscr.refresh()
                            
                            episode_list = [f"Episode {num}" for num in episodes.keys()]
                            selected_episode_idx = display_menu(stdscr, episode_list)
                            
                            curses.endwin()
                            episode_num = list(episodes.keys())[selected_episode_idx]
                            video_id = episodes[episode_num]
                            
                            if debug_mode:
                                print(f"[DEBUG] ID de la vidéo: {video_id}")
                            else:
                                print(f"⏳ Récupération de l'épisode {episode_num}...")
                                
                            video_url = downloader.get_video_url(video_id)
                            if video_url:
                                if debug_mode:
                                    print(f"[DEBUG] URL de la vidéo: {video_url}")
                                else:
                                    print(f"▶️ Lancement de la lecture...")
                                    
                                if video_url.startswith('//'):
                                    video_url = 'https:' + video_url
                                
                                try:
                                    subprocess.run(['mpv', video_url, '--fullscreen'], check=True)
                                    add_to_history(
                                        anime_name=animes[selected_anime],
                                        episode=f"Episode {episode_num}",
                                        saison=selected_season['name'],
                                        url=season_url,
                                        debug=debug_mode
                                    )
                                except subprocess.CalledProcessError as e:
                                    if debug_mode:
                                        print(f"[DEBUG] Erreur lors du lancement de MPV: {e}")
                                    else:
                                        print(f"✗ Erreur lors du lancement de MPV")
                                except FileNotFoundError:
                                    print("✗ Erreur: MPV n'est pas installé sur votre système")
                            else:
                                print("✗ Impossible de récupérer l'URL de la vidéo")
                        else:
                            print("ℹ Aucun épisode trouvé")
                    else:
                        print("✗ Impossible de récupérer la liste des épisodes")
                    
                except Exception as e:
                    if debug_mode:
                        print(f"[DEBUG] Erreur: {e}")
                    return
                
            except Exception as e:
                if debug_mode:
                    print(f"[DEBUG] Erreur: {e}")
                return
                
        except Exception as e:
            if debug_mode:
                print(f"\n[DEBUG] Une erreur s'est produite : {str(e)}")
            else:
                print(f"\n✗ Une erreur s'est produite")
            try:
                curses.endwin()
            except:
                pass
    except Exception as e:
        if debug_mode:
            print(f"\n[DEBUG] Une erreur s'est produite : {str(e)}")
        else:
            print(f"\n✗ Une erreur s'est produite")
        try:
            curses.endwin()
        except:
            pass

if __name__ == "__main__":
    try:
        if "--help" in sys.argv or "-h" in sys.argv:
            display_help()
        elif "--continue" in sys.argv or "-c" in sys.argv or "-cf" in sys.argv:
            full_check = "--full" in sys.argv or "-f" in sys.argv or "-cf" in sys.argv
            sys.argv = [arg for arg in sys.argv if arg not in ["-c", "--continue", "-f", "--full", "-cf"]]
            if len(sys.argv) == 1:
                # Initialize database
                init_db()
                wrapper(lambda stdscr: display_history(stdscr, full_check))
            else:
                wrapper(main)
        elif '--planing' in sys.argv or '-p' in sys.argv:
            curses.wrapper(afficher_planning)
        elif '--upcoming' in sys.argv or '-up' in sys.argv:
            curses.wrapper(display_upcoming)
        else:
            # Initialize or migrate database
            migrate_history_table()
            if len(sys.argv) > 1:
                wrapper(main)
            else:
                wrapper(main)
    except KeyboardInterrupt:
        print("\nProgramme interrompu par l'utilisateur")
    except Exception as e:
        print(f"\nUne erreur s'est produite : {str(e)}")

