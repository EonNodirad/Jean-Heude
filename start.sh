#!/bin/bash
# Jean-Heude — Lancement complet (services Docker + backend hôte)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend_python"

# ============================================================
# 1. Vérification des dépendances système
# ============================================================
echo "Vérification des dépendances système..."

if ! command -v docker &>/dev/null; then
  echo "ERREUR : Docker n'est pas installé."
  echo "Installe-le avec : https://docs.docker.com/engine/install/"
  exit 1
fi

# Accepte à la fois 'docker compose' (plugin v2) et 'docker-compose' (v1)
if docker compose version &>/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null; then
  COMPOSE_CMD="docker-compose"
else
  echo "ERREUR : Docker Compose n'est pas installé."
  echo "Installe-le avec : https://docs.docker.com/compose/install/"
  exit 1
fi

if ! command -v python3 &>/dev/null; then
  echo "ERREUR : Python 3 n'est pas installé."
  exit 1
fi

if ! command -v node &>/dev/null; then
  echo "AVERTISSEMENT : Node.js non détecté — les serveurs MCP ne seront pas installés."
  NODE_AVAILABLE=false
else
  NODE_AVAILABLE=true
fi

echo "Docker     : $(docker --version)"
echo "Compose    : $($COMPOSE_CMD version --short 2>/dev/null || echo 'v1')"
echo "Python     : $(python3 --version)"
$NODE_AVAILABLE && echo "Node.js    : $(node --version)"
echo ""

# ============================================================
# 2. Lancement des services Docker
# ============================================================
echo "Démarrage des services Docker (Qdrant, Neo4j, TTS, STT, Frontend)..."
cd "$SCRIPT_DIR"
$COMPOSE_CMD up -d
echo "Services Docker démarrés."
echo ""

# ============================================================
# 3. Venv Python + dépendances
# ============================================================
cd "$BACKEND_DIR"

if [ ! -d ".venv" ]; then
  echo "Création du venv Python dans backend_python/.venv ..."
  python3 -m venv .venv
fi

source .venv/bin/activate

echo "Installation/mise à jour des dépendances Python (requirements.txt)..."
pip install -r "$BACKEND_DIR/requirements.txt" -q

# ============================================================
# 4. Dépendances Node.js pour les serveurs MCP privés
# ============================================================
if $NODE_AVAILABLE && [ -d "$BACKEND_DIR/mcp_servers_prive" ]; then
  for dir in "$BACKEND_DIR"/mcp_servers_prive/*/; do
    if [ -f "$dir/package.json" ] && [ ! -d "$dir/node_modules" ]; then
      echo "npm install dans $(basename "$dir")..."
      (cd "$dir" && npm install --silent)
    fi
  done
fi

# ============================================================
# 5. Lancement des gateways en arrière-plan (avec PID files)
# ============================================================
GATEWAY_PIDS=()
PID_DIR="$SCRIPT_DIR/.pids"
mkdir -p "$PID_DIR"

start_gateway() {
  local name="$1"
  local script="$2"
  local pid_file="$PID_DIR/${name}.pid"
  local script_basename
  script_basename=$(basename "$script")

  # Tuer toute instance existante par nom de script (fiable même sans PID file)
  pkill -f "$script_basename" 2>/dev/null || true
  sleep 1

  # Nettoyer aussi le PID file si présent
  rm -f "$pid_file"

  python3 "$script" &
  local new_pid=$!
  echo "$new_pid" > "$pid_file"
  GATEWAY_PIDS+=($new_pid)
  echo "  PID $name : $new_pid"
}

# Telegram gateway (uniquement si le token est configuré)
if grep -q "^TELEGRAM_BOT_TOKEN=.\+" "$BACKEND_DIR/.env" 2>/dev/null; then
  echo "Démarrage de la gateway Telegram..."
  start_gateway "telegram" "$BACKEND_DIR/telegram_gateway.py"
else
  echo "AVERTISSEMENT : TELEGRAM_BOT_TOKEN absent — gateway Telegram ignorée."
fi

# Discord gateway (uniquement si le token est configuré)
if grep -q "^DISCORD_BOT_TOKEN=.\+" "$BACKEND_DIR/.env" 2>/dev/null; then
  echo "Démarrage de la gateway Discord..."
  start_gateway "discord" "$BACKEND_DIR/discord_gateway.py"
else
  echo "AVERTISSEMENT : DISCORD_BOT_TOKEN absent — gateway Discord ignorée."
fi

# Nettoyage des gateways à l'arrêt (Ctrl+C)
cleanup() {
  echo ""
  echo "Arrêt des gateways..."
  for pid in "${GATEWAY_PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  rm -f "$PID_DIR"/*.pid
  echo "Arrêt du backend."
  exit 0
}
trap cleanup SIGINT SIGTERM

# ============================================================
# 6. Lancement du backend (au premier plan)
# ============================================================
echo ""
echo "Backend Jean-Heude sur http://0.0.0.0:8000"
echo "Swagger    : http://localhost:8000/docs"
echo "Frontend   : http://localhost:3004"
echo ""

cd "$BACKEND_DIR"
uvicorn main:app --host 0.0.0.0 --port 8000
