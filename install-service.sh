#!/bin/bash
# Jean-Heude — Installation automatique des services systemd
# Usage : sudo bash install-service.sh
set -e

CURRENT_USER=$(logname 2>/dev/null || whoami)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=============================="
echo " Jean-Heude — Install Service"
echo "=============================="
echo ""
echo "Utilisateur détecté : $CURRENT_USER"
echo "Chemin du projet     : $PROJECT_DIR"
echo ""

# Vérifications
for svc in jean-heude-backend.service jean-heude-telegram.service jean-heude-discord.service; do
  if [ ! -f "$PROJECT_DIR/$svc" ]; then
    echo "ERREUR : $svc introuvable dans $PROJECT_DIR"
    exit 1
  fi
done

if [ ! -f "$PROJECT_DIR/backend_python/.env" ]; then
  echo "AVERTISSEMENT : backend_python/.env absent — crée-le avant de démarrer les services."
fi

echo "Ce script va :"
echo "  1. Remplacer les placeholders dans les 3 fichiers .service"
echo "  2. Les copier dans /etc/systemd/system/"
echo "  3. Lancer systemctl daemon-reload"
echo ""
read -p "Continuer ? [o/N] " -n 1 -r
echo ""
[[ ! $REPLY =~ ^[OoYy]$ ]] && { echo "Annulé."; exit 0; }

# Substitution et installation des 3 services
install_service() {
  local src="$PROJECT_DIR/$1"
  local dest="/etc/systemd/system/$1"
  local TMP
  TMP=$(mktemp)
  sed \
    -e "s|<TON_USER>|$CURRENT_USER|g" \
    -e "s|<CHEMIN_ABSOLU>|$PROJECT_DIR|g" \
    "$src" > "$TMP"
  sudo cp "$TMP" "$dest"
  rm "$TMP"
  sudo chmod 644 "$dest"
  echo "✓ $1 installé"
}

install_service jean-heude-backend.service
install_service jean-heude-telegram.service
install_service jean-heude-discord.service

sudo systemctl daemon-reload
echo ""

# Rebuild Docker en mode production
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

# Activer au boot
read -p "Activer les 3 services au démarrage automatique ? [o/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[OoYy]$ ]]; then
  sudo systemctl enable jean-heude-backend jean-heude-telegram jean-heude-discord
  echo "✓ Services activés au boot."
fi
echo ""

# Démarrer maintenant
read -p "Démarrer les 3 services maintenant ? [o/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[OoYy]$ ]]; then
  sudo systemctl start jean-heude-backend
  sleep 2
  sudo systemctl start jean-heude-telegram jean-heude-discord
  echo ""
  systemctl status jean-heude-backend --no-pager
  echo ""
  systemctl status jean-heude-telegram --no-pager
  echo ""
  systemctl status jean-heude-discord --no-pager
fi

echo ""
echo "Commandes utiles :"
echo "  sudo systemctl start|stop|restart jean-heude-backend"
echo "  sudo systemctl start|stop|restart jean-heude-telegram"
echo "  sudo systemctl start|stop|restart jean-heude-discord"
echo "  journalctl -u jean-heude-backend -f"
echo "  journalctl -u jean-heude-telegram -f"
echo "  journalctl -u jean-heude-discord -f"