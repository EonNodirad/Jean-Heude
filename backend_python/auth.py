import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()
SECRET_PASSWORD = os.getenv("JEAN_HEUDE_SECRET")
DB_PATH = "memory/memoire.db"

def init_auth_db():
    """Crée la table des utilisateurs autorisés si elle n'existe pas"""
    os.makedirs("memory", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS authorized_users 
                 (platform TEXT, user_id TEXT, PRIMARY KEY(platform, user_id))''')
    conn.commit()
    conn.close()

def is_authorized(platform: str, user_id: str) -> bool:
    """Vérifie si un utilisateur est dans la liste blanche"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM authorized_users WHERE platform=? AND user_id=?", (platform, str(user_id)))
    result = c.fetchone()
    conn.close()
    return result is not None

def authorize_user(platform: str, user_id: str):
    """Ajoute un utilisateur à la liste blanche"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO authorized_users (platform, user_id) VALUES (?, ?)", (platform, str(user_id)))
    conn.commit()
    conn.close()
