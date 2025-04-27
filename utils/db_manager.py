import sqlite3
import os
import pathlib
from pathlib import Path

# on stocke la base de données sqlite dans le même dossier que le script principal
SCRIPT_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = SCRIPT_DIR / "history.db"

def get_db_connection():
    # fonction simple pour se connecter à la bdd
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    # crée la table pour l'historique si elle n'existe pas
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        anime_name TEXT NOT NULL,
        episode TEXT NOT NULL,
        saison TEXT NOT NULL,
        url TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

def migrate_history_table():
    # crée la bdd locale et récupère les données de l'ancienne bdd si elle existe
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM history")
    count = cursor.fetchone()['count']
    conn.close()
    
    # If we already have data, no need to do anything
    if count > 0:
        return
        
    # Check for old data in ~/.config first (for users who used previous version)
    # Gestion compatible entre Windows et Linux
    if os.name == 'nt':  # Windows
        old_db_path = Path(os.environ.get('APPDATA')) / "anime-sama" / "history.db"
    else:  # Linux/Unix
        old_db_path = Path.home() / ".config" / "anime-sama" / "history.db"
    
    if old_db_path.exists():
        try:
            # Connect to old database
            old_conn = sqlite3.connect(str(old_db_path))
            old_conn.row_factory = sqlite3.Row
            old_cursor = old_conn.cursor()
            
            # Get all entries from old database
            old_cursor.execute("SELECT anime_name, episode, saison, url FROM history")
            old_entries = old_cursor.fetchall()
            old_conn.close()
            
            if old_entries:
                # Connect to new database
                conn = get_db_connection()
                cursor = conn.cursor()
                
                # Copy entries to new database
                for entry in old_entries:
                    cursor.execute(
                        "INSERT INTO history (anime_name, episode, saison, url) VALUES (?, ?, ?, ?)",
                        (entry['anime_name'], entry['episode'], entry['saison'], entry['url'])
                    )
                
                conn.commit()
                conn.close()
                print("✓ Historique migré avec succès depuis l'ancienne base de données")
                return
        except Exception as e:
            print(f"ℹ Impossible de migrer depuis l'ancienne base de données: {e}")
            pass
    
    # If we get here, we're starting with a fresh empty database
    print("ℹ Création d'une nouvelle base de données locale vide")

def add_to_history(anime_name, episode, saison, url, debug=False):
    # ajoute ou met à jour l'historique de visionnage
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if this anime+season combination already exists
        cursor.execute(
            "SELECT id FROM history WHERE anime_name = ? AND saison = ?",
            (anime_name, saison)
        )
        existing = cursor.fetchone()
        
        if existing:
            # Update the existing entry
            cursor.execute(
                "UPDATE history SET episode = ?, url = ?, timestamp = CURRENT_TIMESTAMP WHERE id = ?",
                (episode, url, existing['id'])
            )
            conn.commit()
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
            conn.commit()
            if debug:
                print("[DEBUG] Ajouté à l'historique avec succès")
            else:
                print("✓ Ajouté à l'historique avec succès")
                
        conn.close()
    except Exception as e:
        if debug:
            print(f"[DEBUG] Erreur lors de l'ajout à l'historique: {e}")
        else:
            print(f"✗ Erreur lors de l'ajout à l'historique")

def get_history_entries():
    # récupère tous les enregistrements de l'historique
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM history ORDER BY timestamp DESC")
    history_entries = cursor.fetchall()
    conn.close()
    return history_entries

def delete_history_entry(entry_id):
    # supprime une entrée de l'historique
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM history WHERE id = ?", (entry_id,))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False 