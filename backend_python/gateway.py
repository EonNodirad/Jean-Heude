# gateway.py
import asyncio
from fastapi import WebSocket

class Gateway:
    def __init__(self, agent_runner):
        self.agent_runner = agent_runner
        self.active_connections: dict[str, WebSocket] = {}
        # 🟢 Action : Dictionnaire de files d'attente indexé par client_id
        self.lanes: dict[str, asyncio.Queue] = {}
        # Dictionnaire pour garder une trace des workers (tâches de fond)
        self.workers: dict[str, asyncio.Task] = {}

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

                    # 🎯 Appel de l'Agent Runner (via ta pipeline)
                    # Note : on passe on_token comme callback pour le streaming
                    from agent_runner import AgentRunner
                    runner = AgentRunner() # Ou utilise l'instance passée au init
                    
                    # On exécute le chat
                    result = await runner.process_chat(content, session_id, on_token)

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
