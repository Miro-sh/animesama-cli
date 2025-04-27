import requests
import re
from bs4 import BeautifulSoup
import curses
import time
import subprocess
from datetime import datetime
from utils.downloader import AnimeDownloader, get_episode_list, HEADERS_BASE
from utils.ui import display_menu, display_upcoming_menu
from utils.db_manager import add_to_history
import platform
import os

def get_player_config():
    # Fonction pour lire la configuration du lecteur à utiliser
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.ini")
    default_player = 0  # 0 = Navigateur, 1 = MPV, 2 = VLC
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                for line in f:
                    if line.startswith('default_player='):
                        value = line.strip().split('=')[1]
                        if value.isdigit():
                            default_player = int(value)
        except:
            pass
    
    return default_player

def play_video(video_url, debug_mode=False):
    # Fonction pour lire une vidéo avec le lecteur configuré
    system = platform.system()
    player_config = get_player_config()
    
    if system == "Windows":
        try:
            if player_config == 1:  # MPV
                if os.path.exists(os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), 'mpv', 'mpv.exe')):
                    batch_path = os.path.join(os.environ.get('USERPROFILE', ''), 'open_with_mpv.bat')
                    subprocess.run([batch_path, video_url], check=True, shell=True)
                    print("Lecture de la vidéo avec MPV")
                    return True
                else:
                    if debug_mode:
                        print("[DEBUG] MPV n'est pas installé, essai de VLC...")
            
            if player_config == 2 or (player_config == 1 and not os.path.exists(os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), 'mpv', 'mpv.exe'))):  # VLC ou fallback si MPV pas trouvé
                vlc_path = os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), 'VideoLAN', 'VLC', 'vlc.exe')
                if os.path.exists(vlc_path):
                    batch_path = os.path.join(os.environ.get('USERPROFILE', ''), 'open_with_vlc.bat')
                    if os.path.exists(batch_path):
                        subprocess.run([batch_path, video_url], check=True, shell=True)
                    else:
                        subprocess.run([vlc_path, video_url], check=True, shell=True)
                    print("Lecture de la vidéo avec VLC")
                    return True
                else:
                    if debug_mode:
                        print("[DEBUG] VLC n'est pas installé, utilisation du navigateur...")
            
            # Fallback sur le navigateur
            import webbrowser
            webbrowser.open(video_url)
            print("Ouverture de la vidéo dans le navigateur par défaut")
            return True
            
        except Exception as e:
            if debug_mode:
                print(f"[DEBUG] Erreur lors du lancement du lecteur: {e}")
            try:
                import webbrowser
                webbrowser.open(video_url)
                print("Ouverture de la vidéo dans le navigateur par défaut")
                return True
            except:
                return False
    else:
        # Linux, macOS
        try:
            subprocess.run(['mpv', video_url, '--fullscreen'], check=True)
            return True
        except:
            try:
                import webbrowser
                webbrowser.open(video_url)
                print("Ouverture de la vidéo dans le navigateur par défaut")
                return True
            except:
                return False

def fetch_and_display_episodes(stdscr, anime_url):
    # récupère et affiche les épisodes d'un anime
    import requests
    import re
    import subprocess
    import platform

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

                # Utiliser la fonction play_video pour lire la vidéo
                success = play_video(video_url, debug_mode=False)
                
                if success:
                    anime_name = anime_url.split('/')[0].replace('-', ' ').title()
                    saison = anime_url.split('/')[1].replace('saison', 'Saison ').capitalize()
                    add_to_history(
                        anime_name=anime_name,
                        episode=f"Episode {episode_num}",
                        saison=saison,
                        url=full_url,
                        debug=False
                    )
                else:
                    print("Erreur lors de la lecture de la vidéo")
                    print("Vérifiez si MPV ou VLC est correctement installé")
            else:
                stdscr.addstr("Impossible de récupérer l'URL de la vidéo\n")
        else:
            stdscr.addstr("Aucun épisode trouvé.\n")
    else:
        stdscr.addstr("Impossible de récupérer la liste des épisodes.\n")

    stdscr.refresh()
    stdscr.getch()

def afficher_planning(stdscr):
    # affiche le planning des animes par jour
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

def display_upcoming(stdscr):
    # affiche les prochains épisodes à sortir
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

        # Afficher le menu avec les animes à venir
        stdscr.clear()
        selected_idx = display_upcoming_menu(stdscr, display_items)
        
    except Exception as e:
        stdscr.clear()
        stdscr.addstr(0, 0, f"Erreur lors de la récupération des animes à venir: {str(e)}")
        stdscr.refresh()
        stdscr.getch()

def search_anime(stdscr, query, vf_mode=False, debug_mode=False):
    # recherche et affiche les animes qui correspondent à la requête
    import subprocess
    import platform

    downloader = AnimeDownloader(debug=debug_mode)
    
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
        
        from utils.downloader import get_seasons
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
                        
                        success = play_video(video_url, debug_mode)
                        
                        if success:
                            add_to_history(
                                anime_name=animes[selected_anime],
                                episode=f"Episode {episode_num}",
                                saison=selected_season['name'],
                                url=season_url,
                                debug=debug_mode
                            )
                        else:
                            print("✗ Erreur lors de la lecture de la vidéo")
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