import os
import asyncio
import aiosqlite
import datetime
import httpx
from fastapi import WebSocket
from croniter import croniter
from dotenv import load_dotenv
import re

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")


class Gateway:
    def __init__(self, agent_runner):
        self.agent_runner = agent_runner
        self.active_connections: dict[str, WebSocket] = {}
        # 🟢 Action : Dictionnaire de files d'attente indexé par client_id
        self.lanes: dict[str, asyncio.Queue] = {}
        # Dictionnaire pour garder une trace des workers (tâches de fond)
        self.workers: dict[str, asyncio.Task] = {}
        
        # 💓 NOUVEAU : Lancement du Heartbeat Universel dès la création de la Gateway !
        self.heartbeat_task = asyncio.create_task(self._universal_heartbeat())
        print("💓 [Gateway] Heartbeat Universel démarré en arrière-plan.")

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        
        # Initialisation de la file d'attente pour ce client spécifique
        self.lanes[client_id] = asyncio.Queue()
        # 🟢 Action : Lancement du worker qui va surveiller cette file
        self.workers[client_id] = asyncio.create_task(self._lane_worker(client_id))
        print(f"📡 Lane activée pour : {client_id}")

    def disconnect(self, client_id: str):
        if client_id in self.workers:
            self.workers[client_id].cancel()
            del self.workers[client_id]
        if client_id in self.lanes:
            del self.lanes[client_id]
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        print(f"🔌 Lane fermée pour : {client_id}")

    async def handle_event(self, client_id: str, data: dict):
        """On ne traite plus directement, on empile dans la Lane."""
        if client_id in self.lanes:
            await self.lanes[client_id].put(data)

    async def _lane_worker(self, client_id: str):
        """Boucle infinie qui traite les messages de la file un par un."""
        websocket = self.active_connections.get(client_id)
        while True:
            try:
                # On attend qu'un message arrive dans la file
                data = await self.lanes[client_id].get()
                
                if data.get("type") == "message":
                    content = data.get("content")
                    session_id = data.get("session_id")

                    async def on_token(token):
                        await websocket.send_json({"type": "token", "content": token})

                    # 🎯 Appel de l'Agent Runner
                    result = await self.agent_runner.process_chat(content, session_id, on_token)

                    # Signal de fin
                    await websocket.send_json({
                        "type": "done",
                        "session_id": result["session_id"],
                        "model": result["model"]
                    })

                # On indique que la tâche est terminée pour passer à la suivante
                self.lanes[client_id].task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ Erreur Lane {client_id}: {e}")

    # ==========================================
    # 🌟 NOUVEAU : SYSTÈME D'ÉVÉNEMENTS (CRONS)
    # ==========================================
    async def _route_message(self, channel: str, message: str):
        """Envoie le résultat de la tâche vers le bon canal."""
        
        # ✈️ ROUTE 1 : TELEGRAM
        if channel == "telegram" and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": f"⏱️ *Tâche Auto*\n\n{message}", "parse_mode": "Markdown"}
            async with httpx.AsyncClient() as client:
                await client.post(url, json=payload)
                print("📨 [Gateway] Message routé vers Telegram.")

        # 🎮 ROUTE 2 : DISCORD
        elif channel == "discord" and os.getenv("DISCORD_BOT_TOKEN") and os.getenv("DISCORD_CHANNEL_ID"):
            token = os.getenv("DISCORD_BOT_TOKEN")
            channel_id = os.getenv("DISCORD_CHANNEL_ID")
            
            url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
            headers = {
                "Authorization": f"Bot {token}",
                "Content-Type": "application/json"
            }
            payload = {"content": f"⏱️ **Tâche Auto de Jean-Heude**\n\n{message}"}
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    print("🎮 [Gateway] Message automatique routé vers Discord.")
                else:
                    print(f"❌ [Gateway] Erreur Discord : {response.text}")

        # 🖥️ ROUTE 3 : SVELTE / TAURI
        elif channel == "svelte":
            # On ne fait plus de INSERT INTO ici, car process_chat l'a DÉJÀ fait proprement 
            # dans la bonne session !
            
            # On se contente de rafraîchir l'écran si ton app est ouverte
            for client_id, ws in self.active_connections.items():
                try:
                    await ws.send_json({"type": "proactive_message", "content": message})
                    print(f"🖥️ [Gateway] Message poussé en direct sur le WebSocket de {client_id}.")
                except:
                    pass
        else:
            print(f"⚠️ [Gateway] Canal inconnu : {channel}")

    async def _execute_task(self, task_id: int, prompt: str, channel: str):
        """Fait réfléchir Jean-Heude en tâche de fond en utilisant son VRAI cerveau."""
        print(f"⚡ [Gateway] Exécution de la tâche {task_id} : {prompt}")
        try:
            reponse_complete = ""
            
            async def background_stream(token):
                nonlocal reponse_complete
                clean_token = re.sub(r'\|\|AUDIO_ID:.*?\|\|', '', token)
                if clean_token and not clean_token.startswith("¶"):
                    reponse_complete += clean_token

            # 🎯 VRAIE RÉCUPÉRATION DE LA SESSION ACTIVE
            last_session_id = 1
            try:
                async with aiosqlite.connect("memory/memoire.db") as db:
                    # On utilise rowid qui marche à 100% sur SQLite
                    cursor = await db.execute("SELECT rowid FROM historique_chat ORDER BY timestamp DESC LIMIT 1")
                    row = await cursor.fetchone()
                    if row:
                        last_session_id = row[0]
            except Exception as e:
                print(f"⚠️ Erreur récupération session : {e}")

            instruction_cachee = f"⏱️ [TÂCHE PLANIFIÉE] {prompt}"
            
            # 👻 LA MAGIE OPÈRE ICI : is_hidden=True
            await self.agent_runner.process_chat(
                instruction_cachee, 
                session_id=last_session_id, 
                on_token_callback=background_stream,
                is_hidden=True
            )
            
            parts = re.split(r'\*Utilisation de l\'outil :.*?\*', reponse_complete)
            reponse_finale = parts[-1]
            final_text = re.sub(r'<think>.*?(</think>|$)', '', reponse_finale, flags=re.DOTALL).strip()
            
            if final_text:
                await self._route_message(channel, final_text)
            else:
                print(f"⚠️ [Gateway] La tâche {task_id} n'a produit aucun texte.")
                
        except Exception as e:
            print(f"❌ [Gateway] Erreur exécution tâche {task_id} : {e}")
            
    async def _universal_heartbeat(self):
        """Le Cœur : vérifie l'agenda toutes les minutes."""
        while True:
            try:
                maintenant = datetime.datetime.now()
                async with aiosqlite.connect("memory/tasks.db") as db:
                    cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scheduled_tasks'")
                    if await cursor.fetchone():
                        cursor = await db.execute("SELECT id, prompt, cron_expression, channel FROM scheduled_tasks")
                        tasks = await cursor.fetchall()
                        
                        for task_id, prompt, cron_expr, channel in tasks:
                            if croniter.match(cron_expr, maintenant):
                                # On lance la tâche sans bloquer la boucle
                                asyncio.create_task(self._execute_task(task_id, prompt, channel))
            except Exception as e:
                print(f"❌ [Gateway Heartbeat] Erreur BDD : {e}")
                
            # Calcule le temps restant jusqu'à la prochaine minute exacte (ex: XX:XX:00)
            secondes_restantes = 60 - datetime.datetime.now().second
            await asyncio.sleep(secondes_restantes)
