import sqlite3
import os
import hashlib
import secrets
import logging
import jwt
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("jean_heude.auth")

# ✅ CHEMIN GLOBAL POUR L'AUTHENTIFICATION
DB_PATH = "memory/auth.db"

# ✅ CLEF JWT
_raw_secret = os.getenv("JEAN_HEUDE_SECRET", "")
if len(_raw_secret) < 32:
    if _raw_secret:
        logger.warning(
            "JEAN_HEUDE_SECRET est trop court (%d caractères). "
            "Un secret temporatoire aléatoire est utilisé — les sessions ne survivront pas aux redémarrages. "
            "Définissez une valeur d'au moins 32 caractères dans votre .env.",
            len(_raw_secret),
        )
    SECRET_KEY = secrets.token_hex(32)
else:
    SECRET_KEY = _raw_secret
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def revoke_token(token: str) -> None:
    """Ajoute le token à la blacklist jusqu'à son expiry."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp = payload.get("exp")
    except jwt.PyJWTError:
        return
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO revoked_tokens (token, expires_at) VALUES (?, ?)",
        (token, exp)
    )
    conn.commit()
    conn.close()

def is_token_revoked(token: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT 1 FROM revoked_tokens WHERE token = ?", (token,)
    ).fetchone()
    conn.close()
    return row is not None

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    if is_token_revoked(token):
        return None
    return payload


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
        password_salt BLOB,
        is_admin INTEGER NOT NULL DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        last_active TEXT
    )''')
    # Migration : ajouter les colonnes manquantes si la table existe déjà
    for col, definition in [
        ("is_admin", "INTEGER NOT NULL DEFAULT 0"),
        ("created_at", "TEXT"),  # SQLite n'accepte pas DEFAULT (datetime('now')) en ALTER TABLE
        ("last_active", "TEXT"),
    ]:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
        except Exception:
            pass
    
    # 2. Table des liaisons (Les portes d'entrée vers le compte)
    c.execute('''CREATE TABLE IF NOT EXISTS platform_links (
        platform TEXT,
        platform_user_id TEXT,
        user_id TEXT,
        PRIMARY KEY(platform, platform_user_id),
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )''')

    # 3. Blacklist des tokens révoqués (logout)
    c.execute('''CREATE TABLE IF NOT EXISTS revoked_tokens (
        token TEXT PRIMARY KEY,
        expires_at INTEGER NOT NULL
    )''')

    # 4. Codes OTP pour lier Discord/Telegram sans envoyer le mot de passe
    c.execute('''CREATE TABLE IF NOT EXISTS link_codes (
        code TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        expires_at INTEGER NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )''')

    # Nettoyage des entrées expirées au démarrage
    now_ts = int(datetime.now(timezone.utc).timestamp())
    c.execute("DELETE FROM revoked_tokens WHERE expires_at < ?", (now_ts,))
    c.execute("DELETE FROM link_codes WHERE expires_at < ?", (now_ts,))

    conn.commit()
    conn.close()

def setup_new_user_workspace(user_id: str):
    """🪄 Crée l'arborescence complète et les fichiers par défaut (USER, AGENTS, MEMORY)."""
    base_path = f"memory/users/{user_id}"
    system_path = f"{base_path}/system"
    
    os.makedirs(system_path, exist_ok=True)
    os.makedirs(f"{base_path}/projects", exist_ok=True)
    
    # 1. USER.md (Profil)
    user_md_path = f"{system_path}/USER.md"
    if not os.path.exists(user_md_path):
        with open(user_md_path, "w", encoding="utf-8") as f:
            f.write(f"# Profil de l'utilisateur : {user_id}\n\n")
            f.write("Je suis un nouvel utilisateur sur le système. Apprends à me connaître au fil de nos conversations !\n")
            
    # 2. AGENTS.md (Identité de l'IA)
    agents_md_path = f"{system_path}/AGENTS.md"
    if not os.path.exists(agents_md_path):
        with open(agents_md_path, "w", encoding="utf-8") as f:
            f.write("# Identité Système\n\n")
            f.write(f"Tu es Jean-Heude, l'assistant personnel IA de {user_id}. Sois franc, direct et efficace.\n")

    # 3. ✨ NOUVEAU : MEMORY.md (Journal des faits extraits)
    memory_md_path = f"{system_path}/MEMORY.md"
    if not os.path.exists(memory_md_path):
        with open(memory_md_path, "w", encoding="utf-8") as f:
            f.write(f"# 🧠 Mémoire à long terme de {user_id}\n\n")
            f.write("--- SOUVENIRS ET FAITS EXTRAITS ---\n")
            f.write("(C'est ici que je stocke ce que je retiens de nos échanges importants)\n")
            
    logger.info("Espace de travail initialisé pour : %s", user_id)

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
    
    setup_new_user_workspace(user_id)
    ensure_first_admin(user_id)
    logger.info("Nouveau compte global créé : %s", user_id)
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
    
    logger.info("Lien créé : %s (%s) -> compte %s", platform, platform_user_id, global_user_id)
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

def generate_link_code(user_id: str) -> str:
    """Génère un code OTP à 6 chiffres pour lier Discord/Telegram sans mot de passe."""
    import random
    code = f"{random.randint(0, 999999):06d}"
    expires_at = int((datetime.now(timezone.utc) + timedelta(minutes=10)).timestamp())
    conn = sqlite3.connect(DB_PATH)
    # Un seul code actif par utilisateur
    conn.execute("DELETE FROM link_codes WHERE user_id = ?", (user_id,))
    conn.execute(
        "INSERT INTO link_codes (code, user_id, expires_at) VALUES (?, ?, ?)",
        (code, user_id, expires_at)
    )
    conn.commit()
    conn.close()
    logger.info("Code de liaison généré pour : %s", user_id)
    return code

def redeem_link_code(code: str, platform: str, platform_user_id: str) -> str | None:
    """Échange un code OTP contre un lien plateforme. Retourne le user_id si succès."""
    now_ts = int(datetime.now(timezone.utc).timestamp())
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT user_id, expires_at FROM link_codes WHERE code = ?", (code,)
    ).fetchone()
    if not row or row[1] < now_ts:
        conn.close()
        return None
    user_id = row[0]
    conn.execute(
        "INSERT OR REPLACE INTO platform_links (platform, platform_user_id, user_id) VALUES (?, ?, ?)",
        (platform, str(platform_user_id), user_id)
    )
    conn.execute("DELETE FROM link_codes WHERE code = ?", (code,))
    conn.commit()
    conn.close()
    logger.info("Code OTP utilisé : %s (%s) → %s", platform, platform_user_id, user_id)
    return user_id

def verify_password(user_id: str, password: str) -> dict | None:
    """Vérifie le mot de passe. Retourne les infos du compte ou None si échec."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT password_hash, password_salt, is_admin FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return None
    stored_hash, salt, is_admin = row
    attempt_hash, _ = hash_password(password, salt)
    if attempt_hash != stored_hash:
        conn.close()
        return None
    # Mise à jour de last_active
    c.execute("UPDATE users SET last_active = datetime('now') WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"user_id": user_id, "is_admin": bool(is_admin)}

def set_admin(user_id: str, is_admin: bool) -> bool:
    """Passe un compte en admin (ou retire le rôle)."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("UPDATE users SET is_admin = ? WHERE user_id = ?", (int(is_admin), user_id)).rowcount
    conn.commit()
    conn.close()
    return rows > 0

def ban_user(user_id: str) -> bool:
    """Désactive un compte (is_admin=-1 signale le ban)."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("UPDATE users SET is_admin = -1 WHERE user_id = ?", (user_id,)).rowcount
    conn.commit()
    conn.close()
    return rows > 0

def delete_user(user_id: str) -> bool:
    """Supprime un compte et ses liaisons plateformes."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM platform_links WHERE user_id = ?", (user_id,))
    rows = conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,)).rowcount
    conn.commit()
    conn.close()
    return rows > 0

def list_users() -> list[dict]:
    """Retourne tous les comptes pour le dashboard admin."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT user_id, is_admin, created_at, last_active FROM users ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def ensure_first_admin(user_id: str) -> None:
    """Passe le compte en admin si c'est le premier utilisateur créé."""
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    if count == 1:
        set_admin(user_id, True)
        logger.info("Premier compte — admin attribué automatiquement : %s", user_id)