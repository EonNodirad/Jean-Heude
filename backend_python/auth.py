import sqlite3
import os
import hashlib
import secrets
from dotenv import load_dotenv

load_dotenv()

# ✅ CHEMIN GLOBAL POUR L'AUTHENTIFICATION
DB_PATH = "memory/auth.db"

def hash_password(password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    """Sécurise le mot de passe (ne jamais stocker en clair)."""
    if salt is None:
        salt = secrets.token_bytes(16) # Crée un sel unique
    # Utilisation de pbkdf2_hmac (inclus dans Python) pour une vraie sécurité
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return hashed, salt

def init_auth_db():
    """Crée l'architecture de base de données relationnelle pour l'Omnicanal."""
    os.makedirs("memory", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 1. Table centrale des comptes (Le cœur du système)
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        password_hash BLOB,
        password_salt BLOB
    )''')
    
    # 2. Table des liaisons (Les portes d'entrée vers le compte)
    c.execute('''CREATE TABLE IF NOT EXISTS platform_links (
        platform TEXT,
        platform_user_id TEXT,
        user_id TEXT,
        PRIMARY KEY(platform, platform_user_id),
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )''')
    
    conn.commit()
    conn.close()

def setup_new_user_workspace(user_id: str):
    """🪄 Crée l'arborescence complète et les fichiers par défaut."""
    base_path = f"memory/users/{user_id}"
    system_path = f"{base_path}/system"
    
    os.makedirs(system_path, exist_ok=True)
    
    user_md_path = f"{system_path}/USER.md"
    if not os.path.exists(user_md_path):
        with open(user_md_path, "w", encoding="utf-8") as f:
            f.write(f"# Profil de l'utilisateur : {user_id}\n\n")
            f.write("Je suis un nouvel utilisateur sur le système. Apprends à me connaître au fil de nos conversations !\n")
            
    agents_md_path = f"{system_path}/AGENTS.md"
    if not os.path.exists(agents_md_path):
        with open(agents_md_path, "w", encoding="utf-8") as f:
            f.write("# Identité Système\n\n")
            f.write(f"Tu es Jean-Heude, l'assistant personnel IA de {user_id}. Sois franc, direct et efficace.\n")
            
    print(f"📁 Espace de travail initialisé avec succès pour : {user_id}")

def create_global_account(user_id: str, password: str) -> bool:
    """Étape 1 : L'utilisateur crée son compte maître."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Vérifie si le nom d'utilisateur est déjà pris
    c.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
    if c.fetchone():
        conn.close()
        return False # Pseudo déjà utilisé !
        
    hashed, salt = hash_password(password)
    c.execute("INSERT INTO users (user_id, password_hash, password_salt) VALUES (?, ?, ?)", (user_id, hashed, salt))
    conn.commit()
    conn.close()
    
    # On prépare son espace physique instantanément
    setup_new_user_workspace(user_id)
    print(f"🎉 Nouveau compte global créé : {user_id}")
    return True

def link_platform_account(platform: str, platform_user_id: str, global_user_id: str, password: str) -> bool:
    """Étape 2 : L'utilisateur connecte son Discord/Telegram à son compte maître."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 1. On cherche le compte global
    c.execute("SELECT password_hash, password_salt FROM users WHERE user_id=?", (global_user_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False # Le compte global n'existe pas
        
    stored_hash, salt = row
    attempt_hash, _ = hash_password(password, salt)
    
    # 2. Vérification du mot de passe
    if attempt_hash != stored_hash:
        conn.close()
        return False # Mauvais mot de passe !
        
    # 3. Succès ! On crée le pont entre la plateforme et le compte global
    c.execute("INSERT OR REPLACE INTO platform_links (platform, platform_user_id, user_id) VALUES (?, ?, ?)", 
              (platform, str(platform_user_id), global_user_id))
    conn.commit()
    conn.close()
    
    print(f"🔗 Lien créé : {platform} ({platform_user_id}) pointe désormais vers le compte {global_user_id}")
    return True

def get_global_user_id(platform: str, platform_user_id: str) -> str | None:
    """Étape 3 : La Gateway demande 'Qui est cet utilisateur Discord ?'"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM platform_links WHERE platform=? AND platform_user_id=?", (platform, str(platform_user_id)))
    row = c.fetchone()
    conn.close()
    
    # Retourne le vrai pseudo (ex: "noe_01") si le lien existe, sinon None
    return row[0] if row else None

def verify_password(user_id: str, password: str) -> bool:
    """Vérifie simplement le mot de passe pour la connexion Web."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT password_hash, password_salt FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        return False
        
    stored_hash, salt = row
    attempt_hash, _ = hash_password(password, salt)
    return attempt_hash == stored_hash