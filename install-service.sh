#!/bin/bash
# Jean-Heude — Installation automatique du service systemd
# Usage : sudo bash install-service.sh
set -e

CURRENT_USER=$(logname 2>/dev/null || whoami)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_SRC="$PROJECT_DIR/jean-heude-backend.service"
SERVICE_DEST="/etc/systemd/system/jean-heude-backend.service"

echo "=============================="
echo " Jean-Heude — Install Service"
echo "=============================="
echo ""
echo "Utilisateur détecté : $CURRENT_USER"
echo "Chemin du projet     : $PROJECT_DIR"
echo ""

# Vérifications
if [ ! -f "$SERVICE_SRC" ]; then
  echo "ERREUR : jean-heude-backend.service introuvable dans $PROJECT_DIR"
  exit 1
fi

if [ ! -f "$PROJECT_DIR/backend_python/.env" ]; then
  echo "AVERTISSEMENT : backend_python/.env absent — crée-le avant de démarrer le service."
fi

echo "Ce script va :"
echo "  1. Remplacer les placeholders dans jean-heude-backend.service"
echo "  2. Copier le service dans /etc/systemd/system/"
echo "  3. Lancer systemctl daemon-reload"
echo ""
read -p "Continuer ? [o/N] " -n 1 -r
echo ""
[[ ! $REPLY =~ ^[OoYy]$ ]] && { echo "Annulé."; exit 0; }

# Substitution des placeholders
TMP=$(mktemp)
sed \
  -e "s|<TON_USER>|$CURRENT_USER|g" \
  -e "s|<CHEMIN_ABSOLU>|$PROJECT_DIR|g" \
  "$SERVICE_SRC" > "$TMP"

sudo cp "$TMP" "$SERVICE_DEST"
rm "$TMP"
sudo chmod 644 "$SERVICE_DEST"

sudo systemctl daemon-reload
echo ""
echo "✓ Service installé dans $SERVICE_DEST"
echo ""

# Rebuild Docker en mode production (NODE_ENV=production → .env.production)
read -p "Rebuilder les containers Docker en mode production ? [o/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[OoYy]$ ]]; then
  cd "$PROJECT_DIR"
  if docker compose version &>/dev/null 2>&1; then
    docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
  else
    docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
  fi
  echo "✓ Containers relancés en mode prod."
  cd -
fi
echo ""

read -p "Activer le démarrage automatique au boot ? [o/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[OoYy]$ ]]; then
  sudo systemctl enable jean-heude-backend
  echo "✓ Service activé au boot."
fi

echo ""
read -p "Démarrer le service maintenant ? [o/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[OoYy]$ ]]; then
  sudo systemctl start jean-heude-backend
  sleep 2
  echo ""
  systemctl status jean-heude-backend --no-pager
fi

echo ""
echo "Commandes utiles :"
echo "  sudo systemctl start jean-heude-backend"
echo "  sudo systemctl stop jean-heude-backend"
echo "  journalctl -u jean-heude-backend -f"
