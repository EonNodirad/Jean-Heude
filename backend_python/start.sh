#!/bin/bash

echo "🚀 Démarrage de l'API Svelte/FastAPI..."
uvicorn main:app --host 0.0.0.0 --port 8000 &

echo "📱 Démarrage de la Gateway Telegram..."
python telegram_gateway.py &

echo "🎮 Démarrage de la Gateway Discord..."
python discord_gateway.py &

# La commande 'wait -n' permet de garder le conteneur en vie.
# Si l'un des trois scripts crash, le conteneur s'arrêtera proprement.
wait -n
