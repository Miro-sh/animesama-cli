#!/usr/bin/env python3
# Script principal pour Anime-Sama CLI

import sys
import curses
import os
import locale
from curses import wrapper

# Configuration de l'encodage pour Windows
if os.name == 'nt':  # Windows
    # Force l'encodage UTF-8 pour les caractères spéciaux
    import subprocess
    try:
        # Tente de configurer la console Windows pour utiliser UTF-8
        subprocess.run(["chcp", "65001"], shell=True, check=False)
        # Configure l'encodage pour Python
        os.system("")  # Active le support ANSI sur Windows
    except Exception:
        pass
    
    # Configure la locale pour Windows
    try:
        locale.setlocale(locale.LC_ALL, 'fr_FR.UTF-8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_ALL, '')
        except:
            pass
else:
    # Configuration pour Linux/Unix
    try:
        locale.setlocale(locale.LC_ALL, '')
    except:
        pass

# Importer nos modules
from db_manager import init_db, migrate_history_table
from ui import display_help, display_history
from features import afficher_planning, display_upcoming, search_anime
from ui import display_menu

def main(stdscr):
    # fonction principale qui gère tout le programme
    try:
        debug_mode = "--debug" in sys.argv
        vf_mode = "--vf" in sys.argv
        if debug_mode:
            sys.argv.remove("--debug")
        if vf_mode:
            sys.argv.remove("--vf")
        
        if len(sys.argv) == 1:
            # Menu principal
            # Utilise des émojis compatibles entre plateformes
            menu_options = ["🔍 Recherche", "📜 Historique", "📅 Planning", "🔜 À venir"]
            stdscr.clear()
            
            selected_option = display_menu(stdscr, menu_options)
            curses.endwin()
            
            if selected_option == 0:
                query = input("Entrez le nom de l'anime que vous recherchez : ")
                if query.strip():
                    search_anime(stdscr, query, vf_mode, debug_mode)
            elif selected_option == 1:
                display_history(stdscr)
            elif selected_option == 2:
                afficher_planning(stdscr)
            elif selected_option == 3:
                display_upcoming(stdscr)
        else:
            # Recherche directe avec les arguments de la ligne de commande
            query = " ".join(sys.argv[1:])
            if query.strip():
                search_anime(stdscr, query, vf_mode, debug_mode)
    
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
    # point d'entrée du programme qui gère les arguments
    try:
        # Initialiser la BDD
        init_db()

        if "--help" in sys.argv or "-h" in sys.argv:
            display_help()
        elif "--continue" in sys.argv or "-c" in sys.argv or "-cf" in sys.argv:
            full_check = "--full" in sys.argv or "-f" in sys.argv or "-cf" in sys.argv
            sys.argv = [arg for arg in sys.argv if arg not in ["-c", "--continue", "-f", "--full", "-cf"]]
            wrapper(lambda stdscr: display_history(stdscr, full_check))
        elif '--planing' in sys.argv or '-p' in sys.argv:
            curses.wrapper(afficher_planning)
        elif '--upcoming' in sys.argv or '-up' in sys.argv:
            curses.wrapper(display_upcoming)
        else:
            migrate_history_table()
            wrapper(main)
    except KeyboardInterrupt:
        print("\nProgramme interrompu par l'utilisateur")
    except Exception as e:
        print(f"\nUne erreur s'est produite : {str(e)}")

