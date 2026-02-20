from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
import os
import httpx
from gateway import Gateway
from agent_runner import AgentRunner
import memory
import aiosqlite
import re
import asyncio
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from qdrant_client.http import models  # <-- NOUVEL IMPORT POUR QDRANT

load_dotenv()
STT_SERVER_URL = os.getenv("STT_SERVER_URL")
FRONTEND_URL = os.getenv("FRONTEND_URL")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- PHASE DE DÉMARRAGE ---
    print("🚀 Initialisation de Jean-Heude...")
    
    # 1. Base SQL (Historique & Index Mots-clés)
    async with aiosqlite.connect("memory/memoire.db") as db:
        await db.execute("CREATE TABLE IF NOT EXISTS memory_chat (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, timestamp TIMESTAMP, sessionID INTEGER)")
        await db.execute("CREATE TABLE IF NOT EXISTS historique_chat (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TIMESTAMP, resume TEXT, userID TEXT)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS long_term_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chunk_text TEXT,
                vector_id TEXT -- Lien vers l'ID dans Qdrant
            )""")
        await db.commit()

    # 2. Base Vectorielle Qdrant (Sens)
    try:
        await memory.client_qdrant.get_collection("jean_heude_memories")
    except Exception:
        print("📦 Création de la collection Qdrant 'jean_heude_memories'...")
        await memory.client_qdrant.create_collection(
            collection_name="jean_heude_memories",
            vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
        )

    # 3. Synchronisation du fichier Markdown vers les bases
    await memory.sync_memory_md()

    # 4. Chargement des outils
    await memory.get_tools()  
    
    print("✅ Jean-Heude est prêt !")
    asyncio.create_task(memory.cleanup_audio_store())
    yield
    
    # --- PHASE DE FERMETURE ---
    print("💤 Extinction...")

if not os.path.exists("memory"):
    os.makedirs("memory")

app = FastAPI(lifespan=lifespan)
agent_runner = AgentRunner()
gateway = Gateway(agent_runner)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # L'URL de ton site Svelte
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatInput(BaseModel):
    content : str
    session_id: int | None

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await gateway.connect(websocket, client_id)
    try:
        while True:
            # On reçoit un JSON (ex: {"type": "message", "content": "Salut", "session_id": 1})
            data = await websocket.receive_json()
            await gateway.handle_event(client_id, data)
    except WebSocketDisconnect:
        gateway.disconnect(client_id)

@app.get("/history")
async def get_historique_list():
    async with aiosqlite.connect("memory/memoire.db") as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id, resume, timestamp FROM historique_chat ORDER BY timestamp DESC") as cursor:
            lignes = await cursor.fetchall()
            return [{"id": ligne[0], "resume": ligne[1], "timestamp": ligne[2]} for ligne in lignes]

@app.get("/history/{session_id}")
async def get_history(session_id: int):
    async with aiosqlite.connect("memory/memoire.db") as db:
        async with db.execute("SELECT role, content FROM memory_chat WHERE sessionID = ? ORDER BY timestamp ASC", (session_id,)) as cursor:
            messages = await cursor.fetchall()
            return [{"role": m[0], "content": m[1]} for m in messages]

@app.get("/api/tts/{audio_id}")
async def get_tts(audio_id:str):
    if audio_id not in memory.audio_store:
        return {"error": "ID inconnu"}, 404
    
    try:
        entry = memory.audio_store[audio_id]

        async def chunk_generator():
            await entry["event"].wait()
            chunk_index = 0
            while True:
            # S'il y a de nouveaux chunks, on les envoie
                while chunk_index < len(entry["chunks"]):
                    yield entry["chunks"][chunk_index]
                    chunk_index += 1
            
            # Si la génération est terminée, on s'arrête
                if entry["status"] == "done" and chunk_index >= len(entry["chunks"]):
                    break
                
            # Sinon on attend un peu le prochain morceau
                await asyncio.sleep(0.01)

        return StreamingResponse(chunk_generator(), media_type="application/octet-stream")
    except asyncio.TimeoutError:
        return {"error": "Le TTS est trop lent, abandon."}, 504

@app.post("/stt")
async def voice_endpoint(
    file: UploadFile = File(...), 
    session_id: int = Form(None) # Svelte peut envoyer le session_id en même temps que l'audio
):
    # 1. On récupère le binaire
    audio_binary = await file.read()
    
    # 2. On appelle ton 4ème serveur (STT)
    text_transcribed = ""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {'file': ('audio.wav', audio_binary, 'audio/wav')}
            response = await client.post(STT_SERVER_URL, files=files)
            if response.status_code == 200:
                text_transcribed = response.json().get("text", "")
    except Exception as e:
        print(f"❌ Erreur STT : {e}")
        return {"error": "Serveur STT injoignable"}

    if not text_transcribed:
        return {"error": "Aucune parole détectée"}

    # 3. On injecte le texte transcrit dans la même logique que le chat classique
    print(f"🎤 Transcrit : {text_transcribed}")
    async def dummy_callback(token): pass
    result = await agent_runner.process_chat(text_transcribed, session_id, dummy_callback)
    return {
        "text": text_transcribed, 
        "session_id": result["session_id"],
        "model": result["model"]
    }
