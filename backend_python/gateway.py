import os
import asyncio
import aiosqlite
import datetime
import httpx
import uuid
from fastapi import WebSocket
from croniter import croniter
from dotenv import load_dotenv
import re
import logging

load_dotenv()
logger = logging.getLogger("jean_heude.gateway")
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
        # Capacités déclarées par chaque client (ex: {"client_tools"})
        self.client_capabilities: dict[str, set] = {}
        # Répertoire de travail déclaré par le CLI client
        self.client_working_dirs: dict[str, str] = {}
        # Futures en attente de tool_result, indexées par call_id
        self.pending_tool_calls: dict[str, asyncio.Future] = {}

        # 💓 NOUVEAU : Lancement du Heartbeat Universel dès la création de la Gateway !
        self.heartbeat_task = asyncio.create_task(self._universal_heartbeat())
        logger.info("[Gateway] Heartbeat Universel démarré en arrière-plan.")

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        
        # Initialisation de la file d'attente pour ce client spécifique
        self.lanes[client_id] = asyncio.Queue()
        # 🟢 Action : Lancement du worker qui va surveiller cette file
        self.workers[client_id] = asyncio.create_task(self._lane_worker(client_id))
        logger.info("Lane activée pour : %s", client_id)

    def disconnect(self, client_id: str):
        if client_id in self.workers:
            self.workers[client_id].cancel()
            del self.workers[client_id]
        if client_id in self.lanes:
            del self.lanes[client_id]
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        self.client_capabilities.pop(client_id, None)
        # Annuler les tool_calls en attente pour ce client
        for call_id in list(self.pending_tool_calls.keys()):
            fut = self.pending_tool_calls.pop(call_id)
            if not fut.done():
                fut.cancel()
        logger.info("Lane fermée pour : %s", client_id)

    async def broadcast_system_message(self, message: str):
        """Envoie un message système à tous les clients WebSocket connectés."""
        payload = {"type": "system", "content": message}
        dead = []
        for client_id, ws in list(self.active_connections.items()):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(client_id)
        for client_id in dead:
            self.disconnect(client_id)

    def has_capability(self, client_id: str, capability: str) -> bool:
        return capability in self.client_capabilities.get(client_id, set())

    async def send_tool_call_to_client(self, client_id: str, call_id: str, name: str, args: dict) -> dict:
        """Envoie un tool_call au CLI et attend le tool_result. Timeout 60s."""
        websocket = self.active_connections.get(client_id)
        if not websocket:
            raise RuntimeError(f"Client {client_id} déconnecté")
        loop = asyncio.get_event_loop()
        fut: asyncio.Future = loop.create_future()
        self.pending_tool_calls[call_id] = fut
        try:
            await websocket.send_json({
                "type": "tool_call",
                "call_id": call_id,
                "name": name,
                "args": args,
            })
            result = await asyncio.wait_for(asyncio.shield(fut), timeout=60.0)
            return result
        except asyncio.TimeoutError:
            self.pending_tool_calls.pop(call_id, None)
            raise RuntimeError(f"Timeout : le client n'a pas répondu à l'outil {name}")
        except Exception:
            self.pending_tool_calls.pop(call_id, None)
            raise

    async def handle_event(self, client_id: str, data: dict):
        """Traite les messages entrants : tool_result directement, le reste dans la lane."""
        # tool_result : résoudre la Future correspondante sans passer par la lane
        if data.get("type") == "tool_result":
            call_id = data.get("call_id", "")
            fut = self.pending_tool_calls.pop(call_id, None)
            if fut and not fut.done():
                fut.set_result({
                    "content": data.get("content"),
                    "error": data.get("error"),
                })
            return

        # Stocker les capacités et le répertoire de travail déclarés dès le premier message
        if data.get("type") == "message":
            caps = data.get("capabilities", [])
            if caps:
                self.client_capabilities[client_id] = set(caps)
            working_dir = data.get("working_dir")
            if working_dir:
                self.client_working_dirs[client_id] = working_dir

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
                    content = data.get("content", "")
                    if not content or len(content) > 16000:
                        await websocket.send_json({"type": "error", "content": "Message vide ou trop long (max 16 000 caractères)."})
                        self.lanes[client_id].task_done()
                        continue
                    session_id = data.get("session_id")
                    user_id = data.get("user_id", "invite")
                    async def on_token(token):
                        await websocket.send_json({"type": "token", "content": token})

                    # Tool callback pour les outils côté client (jh CLI)
                    tool_callback = None
                    if self.has_capability(client_id, "client_tools"):
                        async def tool_callback(name: str, args: dict) -> str:
                            call_id = str(uuid.uuid4())
                            result = await self.send_tool_call_to_client(client_id, call_id, name, args)
                            if result.get("error"):
                                return f"[Erreur outil] {result['error']}"
                            return result.get("content") or ""

                    # 🎯 Appel de l'Agent Runner
                    working_dir = self.client_working_dirs.get(client_id)
                    result = await self.agent_runner.process_chat(content, session_id, user_id, on_token, tool_callback=tool_callback, working_dir=working_dir)

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
                logger.error("Erreur Lane %s: %s", client_id, e)

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
                logger.info("[Gateway] Message routé vers Telegram.")

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
                    logger.info("[Gateway] Message automatique routé vers Discord.")
                else:
                    logger.error("[Gateway] Erreur Discord : %s", response.text)

        # 🖥️ ROUTE 3 : SVELTE / TAURI
        elif channel == "svelte":
            # On ne fait plus de INSERT INTO ici, car process_chat l'a DÉJÀ fait proprement 
            # dans la bonne session !
            
            # On se contente de rafraîchir l'écran si ton app est ouverte
            for client_id, ws in self.active_connections.items():
                try:
                    await ws.send_json({"type": "proactive_message", "content": message})
                    logger.debug("[Gateway] Message poussé sur WebSocket de %s.", client_id)
                except Exception:
                    pass
        else:
            logger.warning("[Gateway] Canal inconnu : %s", channel)

    async def _execute_task(self, task_id: int, prompt: str, channel: str, user_id: str):
        """Fait réfléchir Jean-Heude en tâche de fond pour LE BON UTILISATEUR."""
        logger.info("[Gateway] Exécution de la tâche %s pour %s : %s", task_id, user_id, prompt)
        try:
            reponse_complete = ""
            
            async def background_stream(token):
                nonlocal reponse_complete
                clean_token = re.sub(r'\|\|AUDIO_ID:.*?\|\|', '', token)
                if clean_token and not clean_token.startswith("¶"):
                    reponse_complete += clean_token

            # 🎯 VRAIE RÉCUPÉRATION DE LA SESSION ACTIVE DU BON UTILISATEUR
            last_session_id = 1
            try:
                user_db_path = f"memory/users/{user_id}/memoire.db"
                async with aiosqlite.connect(user_db_path) as db:
                    # NOUVEAU : On filtre par userID pour ne pas prendre la session d'un autre !
                    cursor = await db.execute(
                        "SELECT rowid FROM historique_chat WHERE userID = ? ORDER BY timestamp DESC LIMIT 1",
                        (user_id,)
                    )
                    row = await cursor.fetchone()
                    if row:
                        last_session_id = row[0]
            except Exception as e:
                logger.warning("Erreur récupération session pour %s : %s", user_id, e)

            instruction_cachee = f"⏱️ [TÂCHE PLANIFIÉE] {prompt}"
            
            # 👻 LA MAGIE OPÈRE ICI : On utilise le VRAI user_id
            await self.agent_runner.process_chat(
                instruction_cachee, 
                session_id=last_session_id, 
                user_id=user_id,  # ⬅️ Le propriétaire de la tâche !
                on_token_callback=background_stream,
                is_hidden=True
            )
            
            parts = re.split(r'\*Utilisation de l\'outil :.*?\*', reponse_complete)
            reponse_finale = parts[-1]
            final_text = re.sub(r'<think>.*?(</think>|$)', '', reponse_finale, flags=re.DOTALL).strip()
            
            if final_text:
                await self._route_message(channel, final_text)
            else:
                logger.warning("[Gateway] La tâche %s n'a produit aucun texte.", task_id)
                
        except Exception as e:
            logger.error("[Gateway] Erreur exécution tâche %s : %s", task_id, e)
            
    async def _universal_heartbeat(self):
        """Le Cœur : vérifie l'agenda de CHAQUE utilisateur toutes les minutes."""
        while True:
            maintenant = datetime.datetime.now()
            users_dir = "memory/users"
            
            # On vérifie que le dossier principal existe
            if os.path.exists(users_dir):
                # On boucle sur tous les dossiers utilisateurs (ex: noe_01, alice_88)
                for user_id in os.listdir(users_dir):
                    user_task_db = f"{users_dir}/{user_id}/tasks.db"
                    
                    # Si cet utilisateur a des tâches planifiées
                    if os.path.exists(user_task_db):
                        try:
                            async with aiosqlite.connect(user_task_db) as db:
                                cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scheduled_tasks'")
                                if await cursor.fetchone():
                                    # Plus besoin de chercher 'user_id' dans la table, on le connait grâce au dossier !
                                    cursor = await db.execute("SELECT id, prompt, cron_expression, channel FROM scheduled_tasks")
                                    tasks = await cursor.fetchall()
                                    
                                    for task_id, prompt, cron_expr, channel in tasks:
                                        if croniter.match(cron_expr, maintenant):
                                            # On lance la tâche avec le BON utilisateur
                                            asyncio.create_task(self._execute_task(task_id, prompt, channel, user_id))
                        except Exception as e:
                            logger.error("[Heartbeat] Erreur BDD pour %s : %s", user_id, e)

            # Calcule le temps restant jusqu'à la prochaine minute exacte
            secondes_restantes = 60 - datetime.datetime.now().second
            await asyncio.sleep(secondes_restantes)
            
    