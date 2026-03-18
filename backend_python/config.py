"""
Centralisation de toutes les constantes configurables de Jean-Heude.
Les valeurs par défaut peuvent être surchargées via le fichier .env.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# Agent Runner
# ==========================================
# Nombre maximum de tokens avant compaction du contexte
AGENT_MAX_TOKENS: int = int(os.getenv("AGENT_MAX_TOKENS", "5000"))

# Modèle utilisé pour les tâches admin (résumé, extraction de faits)
AGENT_ADMIN_MODEL: str = os.getenv("AGENT_ADMIN_MODEL", "llama3.1:8b")

# Modèle vision pour l'analyse d'images
AGENT_VISION_MODEL: str = os.getenv("AGENT_VISION_MODEL", "openbmb/minicpm-v4.5:8b")

# ==========================================
# Sélection JIT des outils
# ==========================================
# Seuil de similarité cosinus pour la sélection des outils
TOOLS_COSINE_THRESHOLD: float = float(os.getenv("TOOLS_COSINE_THRESHOLD", "0.62"))

# Nombre max d'outils retournés par decide_model
TOOLS_LIMIT_DECIDE: int = int(os.getenv("TOOLS_LIMIT_DECIDE", "10"))

# Nombre max d'outils retournés par chat_with_memories
TOOLS_LIMIT_CHAT: int = int(os.getenv("TOOLS_LIMIT_CHAT", "12"))

# ==========================================
# MCP
# ==========================================
MCP_CONNECT_TIMEOUT: int = int(os.getenv("MCP_CONNECT_TIMEOUT", "10"))
MCP_EXEC_TIMEOUT: int = int(os.getenv("MCP_EXEC_TIMEOUT", "30"))

# ==========================================
# WebSocket / Prompts
# ==========================================
# Longueur maximale d'un prompt utilisateur (caractères)
MAX_PROMPT_LENGTH: int = int(os.getenv("MAX_PROMPT_LENGTH", "16000"))

# ==========================================
# Auth
# ==========================================
ACCESS_TOKEN_EXPIRE_DAYS: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_DAYS", "7"))
LINK_CODE_TTL_MINUTES: int = int(os.getenv("LINK_CODE_TTL_MINUTES", "10"))
