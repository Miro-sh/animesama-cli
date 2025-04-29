import curses
import time
import os
from db_manager import get_history_entries, delete_history_entry
from downloader import AnimeDownloader, get_episode_list
from db_manager import add_to_history

def debug_print(message, debug_mode=False):
    # fonction simple pour afficher des messages de debug
    if debug_mode:
        print(f"[DEBUG] {message}")

def configure_curses_colors():
    # Configure les couleurs de manière compatible avec tous les terminaux
    try:
        curses.start_color()
        # Utilise la couleur par défaut du terminal (-1) si disponible
        # Sinon utilise des couleurs standard
        try:
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_RED, -1)
            curses.init_pair(2, curses.COLOR_BLUE, -1)
            curses.init_pair(3, curses.COLOR_GREEN, -1)
            curses.init_pair(4, curses.COLOR_YELLOW, -1)
        except:
            # Fallback pour les terminaux qui ne supportent pas -1
            curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
            curses.init_pair(2, curses.COLOR_BLUE, curses.COLOR_BLACK)
            curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)
            curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    except:
        pass  # En cas d'erreur, le programme continuera sans couleurs

def display_menu(stdscr, items, urls=None, delete_callback=None):
    # affiche un menu pour naviguer entre les différentes options
    curses.curs_set(0)
    configure_curses_colors()
    stdscr.clear()
    current_row = 0
    scroll_offset = 0

    max_height, max_width = stdscr.getmaxyx()
    max_display = max_height - 2
    margin_top = 2
    
    # Add a title and border
    title = "Anime-Sama Viewer"
    stdscr.addstr(0, max_width//2 - len(title)//2, title, curses.A_BOLD | curses.color_pair(4))
    
    # Symboles compatibles avec Windows et Linux
    up_arrow = "^" if os.name == 'nt' else "↑"
    down_arrow = "v" if os.name == 'nt' else "↓"
    
    while True:
        stdscr.clear()
        
        # Add a title and border
        stdscr.addstr(0, max_width//2 - len(title)//2, title, curses.A_BOLD | curses.color_pair(4))
        stdscr.hline(1, 0, curses.ACS_HLINE, max_width)
        
        position_text = f"[{current_row + 1}/{len(items)}]"
        stdscr.addstr(max_height-1, 0, position_text)
        
        # Add navigation help
        help_text = f"{up_arrow}/{down_arrow}: Navigate | Enter: Select | i: Info | Del: Delete"
        if len(help_text) < max_width:
            stdscr.addstr(max_height-1, max_width - len(help_text) - 1, help_text)
        
        start_idx = scroll_offset
        end_idx = min(len(items), scroll_offset + max_display)
        
        for idx, item in enumerate(items[start_idx:end_idx], start=start_idx):
            x = max_width//2 - len(item)//2
            y = (idx - scroll_offset) + margin_top
            
            if "Dernier Episode" in item:
                try:
                    stdscr.attron(curses.color_pair(1))
                except:
                    pass
            
            if idx == current_row:
                stdscr.attron(curses.A_REVERSE)
                stdscr.addstr(y, x, item[:max_width-1])
                stdscr.attroff(curses.A_REVERSE)
            else:
                stdscr.addstr(y, x, item[:max_width-1])
            
            if "Dernier Episode" in item:
                try:
                    stdscr.attroff(curses.color_pair(1))
                except:
                    pass
            
            if urls:
                try:
                    if "vostfr" in urls[idx].lower():
                        stdscr.attron(curses.color_pair(2))
                        stdscr.addstr(y, x + item.lower().find("vostfr"), "VOSTFR")
                        stdscr.attroff(curses.color_pair(2))
                    elif "vf" in urls[idx].lower():
                        stdscr.attron(curses.color_pair(3))
                        stdscr.addstr(y, x + item.lower().find("vf"), "VF")
                        stdscr.attroff(curses.color_pair(3))
                except:
                    pass  # En cas d'erreur, continue sans couleurs
        
        if scroll_offset > 0:
            stdscr.addstr(margin_top-1, max_width-3, up_arrow)
        if end_idx < len(items):
            stdscr.addstr(max_height-1, max_width-3, down_arrow)
                
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
                import requests
                response = requests.get(urls[current_row], headers={"user-agent": "Mozilla/5.0"})
                response.raise_for_status()
                page_content = response.text
                
                lines = [page_content[i:i+max_width] for i in range(0, len(page_content), max_width)]
                
                for idx, line in enumerate(lines, start=2):
                    if idx < max_height - 1:
                        stdscr.addstr(idx, 0, line)
                
                stdscr.addstr(max_height - 1, 0, "Appuyez sur n'importe quelle touche pour revenir.")
            except Exception as e:
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

def display_history(stdscr, full_check=False):
    # affiche l'historique des animes regardés
    import requests
    import subprocess
    import platform

    def delete_history_callback(index):
        try:
            # Get all history entries
            history_entries = get_history_entries()
            
            if history_entries and 0 <= index < len(history_entries):
                entry_id = history_entries[index]['id']
                
                # Delete the entry
                if delete_history_entry(entry_id):
                    curses.endwin()
                    print("✓ Entrée supprimée de l'historique")
                    time.sleep(1)  # Give user time to see the message
                else:
                    curses.endwin()
                    print("✗ Erreur lors de la suppression")
                    time.sleep(1)
            else:
                curses.endwin()
                print("✗ Entrée introuvable dans l'historique")
                time.sleep(1)
        except Exception as e:
            curses.endwin()
            print(f"✗ Erreur lors de la suppression de l'entrée de l'historique: {e}")
            time.sleep(1)

    try:
        # Get all history entries from the local database
        history_entries = get_history_entries()
        
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
            anime_name = entry['anime_name']
            episode = entry['episode']
            saison = entry['saison']
            url = entry['url']
            
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
        
        selected_idx = display_menu(stdscr, formatted_entries, urls, delete_callback=delete_history_callback)
        
        if selected_idx is not None and selected_idx < len(urls):
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
                    episode_info = entry['episode']
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
                                # Utiliser le lecteur approprié selon le système d'exploitation
                                if os.name == 'nt':  # Windows
                                    # Sur Windows, essayer d'abord MPV si installé, sinon ouvrir avec le navigateur par défaut
                                    try:
                                        subprocess.run(['mpv', video_url, '--fullscreen'], check=True, shell=True)
                                    except (subprocess.CalledProcessError, FileNotFoundError):
                                        # Si MPV n'est pas disponible, utiliser le navigateur par défaut
                                        print("MPV non trouvé, ouverture avec le navigateur par défaut...")
                                        import webbrowser
                                        webbrowser.open(video_url)
                                else:  # Linux/Unix
                                    # Sur Linux, essayer d'utiliser MPV
                                    subprocess.run(['mpv', video_url, '--fullscreen'], check=True)
                                
                                add_to_history(
                                    anime_name=entry['anime_name'],
                                    episode=next_episode_str,
                                    saison=entry['saison'],
                                    url=selected_url,
                                    debug=False
                                )
                            except subprocess.CalledProcessError as e:
                                print(f"✗ Erreur lors du lancement du lecteur vidéo: {e}")
                            except FileNotFoundError:
                                print("✗ Erreur: MPV n'est pas installé. Sur Windows, vous pouvez installer MPV ou le programme essaiera d'utiliser votre navigateur.")
                                # Tenter d'ouvrir avec le navigateur si MPV n'est pas disponible
                                try:
                                    import webbrowser
                                    print("Tentative d'ouverture avec le navigateur...")
                                    webbrowser.open(video_url)
                                    add_to_history(
                                        anime_name=entry['anime_name'],
                                        episode=next_episode_str,
                                        saison=entry['saison'],
                                        url=selected_url,
                                        debug=False
                                    )
                                except Exception as e:
                                    print(f"✗ Impossible d'ouvrir la vidéo: {e}")
                    else:
                        print(f"ℹ {entry['anime_name']} - {episode_info} - {entry['saison']} - Dernier Episode")
                else:
                    print("ℹ Aucun épisode trouvé")
            else:
                print("✗ Impossible de récupérer la liste des épisodes")
            
    except Exception as e:
        curses.endwin()
        print(f"✗ Erreur lors de la lecture de l'historique: {e}")

def display_upcoming_menu(stdscr, items):
    curses.curs_set(0)
    current_row = 0
    scroll_offset = 0
    
    # Configure les couleurs
    configure_curses_colors()
    
    # Symboles compatibles avec Windows et Linux
    up_arrow = "^" if os.name == 'nt' else "↑"
    down_arrow = "v" if os.name == 'nt' else "↓"
    separator = "-" if os.name == 'nt' else "─"
    
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
            # Remplacer les caractères spéciaux si nécessaire
            if os.name == 'nt':
                item = item.replace("─", separator)
                
            x = max_width//2 - len(item)//2
            y = (idx - scroll_offset) + margin_top
            
            if idx == current_row and separator not in item:  # Ne pas mettre en surbrillance les séparateurs
                stdscr.attron(curses.A_REVERSE)
            
            try:
                if curses.has_colors():
                    stdscr.attron(curses.color_pair(color_pair))
                stdscr.addstr(y, x, item[:max_width-1])
                if curses.has_colors():
                    stdscr.attroff(curses.color_pair(color_pair))
            except curses.error:
                stdscr.addstr(y, x, item[:max_width-1])
            
            if idx == current_row and separator not in item:
                stdscr.attroff(curses.A_REVERSE)
        
        if scroll_offset > 0:
            stdscr.addstr(margin_top-1, max_width-3, up_arrow)
        if end_idx < len(items):
            stdscr.addstr(max_height-1, max_width-3, down_arrow)
        
        key = stdscr.getch()
        
        if key == curses.KEY_UP:
            # Trouver le prochain élément non-séparateur vers le haut
            new_row = current_row - 1
            while new_row >= 0 and separator in items[new_row][0]:
                new_row -= 1
            if new_row >= 0:
                current_row = new_row
                if current_row < scroll_offset:
                    scroll_offset = current_row
        elif key == curses.KEY_DOWN:
            # Trouver le prochain élément non-séparateur vers le bas
            new_row = current_row + 1
            while new_row < len(items) and separator in items[new_row][0]:
                new_row += 1
            if new_row < len(items):
                current_row = new_row
                if current_row >= scroll_offset + max_display:
                    scroll_offset = current_row - max_display + 1
        elif key == curses.KEY_ENTER or key in [10, 13]:
            if separator not in items[current_row][0]:  # Ne pas sélectionner les séparateurs
                return current_row
        
        stdscr.refresh()

def display_help():
    # affiche l'aide pour utiliser le script
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