from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from PIL import Image
from fastapi.staticfiles import StaticFiles
import os
import httpx
from gateway import Gateway
from agent_runner import AgentRunner
import memory
import aiosqlite

import asyncio
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from qdrant_client.http import models  
from watchfiles import awatch
import tools 
import base64
import io
import uuid

load_dotenv()
STT_SERVER_URL = os.getenv("STT_SERVER_URL")
FRONTEND_URL = os.getenv("FRONTEND_URL")

async def watch_skills_folder():
    """Surveille le dossier /skills et met à jour Qdrant automatiquement."""
    print("👀 [Auto-Watch] Surveillance du dossier /skills activée...")
    # S'il n'existe pas, on le crée pour éviter que awatch ne plante
    if not os.path.exists("skills"):
        os.makedirs("skills")
        
    # awatch écoute les événements du système de fichiers sans bloquer le serveur !
    async for changes in awatch("skills"):
        print("🔄 [Auto-Watch] Modification détectée dans les skills ! Mise à jour en cours...")
        await tools.sync_skills_to_qdrant()

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

    # 4. Synchronisation de l'App Store JIT
    await tools.sync_skills_to_qdrant()
    
    print("✅ Jean-Heude est prêt !")
    asyncio.create_task(memory.cleanup_audio_store())

    asyncio.create_task(watch_skills_folder())
    yield
    
    # --- PHASE DE FERMETURE ---
    print("💤 Extinction...")

if not os.path.exists("memory"):
    os.makedirs("memory")

app = FastAPI(lifespan=lifespan)
agent_runner = AgentRunner()
gateway = Gateway(agent_runner)

# Création du dossier physique s'il n'existe pas
os.makedirs("memory/uploads", exist_ok=True)
# On dit à FastAPI que tout ce qui commence par /api/uploads pointe vers ce dossier
app.mount("/api/uploads", StaticFiles(directory="memory/uploads"), name="uploads")

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
        db.row_factory = aiosqlite.Row # Permet de récupérer les colonnes par leur nom
        # NOUVEAU : on ajoute 'image' dans le SELECT
        cursor = await db.execute(
            "SELECT role, content, image FROM memory_chat WHERE sessionID = ? ORDER BY timestamp ASC",
            (session_id,)
        )
        lignes = await cursor.fetchall()
        
        # On renvoie tout à Svelte, y compris l'image
        return [{"role": ligne["role"], "content": ligne["content"], "image": ligne["image"]} for ligne in lignes]

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
    session_id: str = Form(None) # Le FormData Svelte envoie souvent une string
):
    # 1. On récupère le binaire audio
    audio_binary = await file.read()
    
    # 2. On appelle ton serveur STT
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

    print(f"🎤 Transcrit : {text_transcribed}")

    # 3. Création / Récupération de la session AVANT le stream (pour les headers)
    if session_id is None or session_id == 'null' or session_id == 'undefined':
        async with aiosqlite.connect("memory/memoire.db") as db:
            resume = text_transcribed[:30] + "..."
            cursor = await db.execute(
                "INSERT INTO historique_chat (timestamp, resume, userID) VALUES (datetime('now'), ?, ?)",
                (resume, "noe_01")
            )
            await db.commit()
            real_session_id = cursor.lastrowid
            print(f"🆕 Session générée dans /stt : {real_session_id}")
    else:
        real_session_id = int(session_id)

    # 4. Le tuyau de Streaming pour le Proxy SvelteKit
    q = asyncio.Queue()

    async def stream_callback(token: str):
        await q.put(token)

    async def run_agent():
        try:
            await agent_runner.process_chat(text_transcribed, real_session_id, stream_callback)
        except Exception as e:
            print(f"❌ Erreur Agent : {e}")
        finally:
            await q.put(None) # Ferme le tuyau à la fin

    # Lancement de la réflexion en tâche de fond
    asyncio.create_task(run_agent())

    async def stream_generator():
        while True:
            token = await q.get()
            if token is None:
                break
            yield token

    # 5. On prépare les Headers EXACTS que ton +server.ts demande
    headers = {
        "x-session-id": str(real_session_id),
        "x-chosen-model": "qwen3:8b" 
    }

    return StreamingResponse(stream_generator(), media_type="text/plain", headers=headers)


@app.post("/api/multimodal")
async def multimodal_endpoint(
    prompt: str = Form(...),
    image: UploadFile = File(None), # L'image est optionnelle
    session_id: str = Form(None)
):
    print(f"📷 Requête multimodale reçue : '{prompt[:20]}...' + Image: {image.filename if image else 'Non'}")
    
    # 1. Gestion de la session (comme pour le STT)
    real_session_id = int(session_id) if session_id and session_id != 'null' else None
    if not real_session_id:
         async with aiosqlite.connect("memory/memoire.db") as db:
            resume = "Analyse d'image: " + prompt[:20] + "..."
            cursor = await db.execute(
                "INSERT INTO historique_chat (timestamp, resume, userID) VALUES (datetime('now'), ?, ?)",
                (resume, "noe_01")
            )
            await db.commit()
            real_session_id = cursor.lastrowid

    # 2. Traitement de l'image (Conversion en Base64 pour Ollama)
    image_b64 = None
    image_path_db = None
    if image:
        contents = await image.read()
        
        # 1. On garde le Base64 pour que Qwen3-VL l'analyse tout de suite
        image_b64 = base64.b64encode(contents).decode('utf-8')

        # 2. COMPRESSION ET SAUVEGARDE POUR L'HISTORIQUE SVELTE
        try:
            img_pil = Image.open(io.BytesIO(contents))
            # On la redimensionne (max 800x800) pour gagner énormément de place
            img_pil.thumbnail((800, 800)) 
            
            # On génère un nom de fichier unique
            filename = f"{uuid.uuid4()}.jpg"
            filepath = f"memory/uploads/{filename}"
            
            # Sauvegarde en JPEG avec une qualité de 70% (invisible à l'œil nu sur un chat, mais très léger)
            img_pil.convert("RGB").save(filepath, "JPEG", quality=70)
            
            # C'est ce lien qu'on va sauvegarder en base de données
            image_path_db = f"/api/uploads/{filename}"
        except Exception as e:
            print(f"❌ Erreur de sauvegarde de l'image : {e}")

    # 3. Le tuyau de Streaming
    q = asyncio.Queue()
    async def stream_callback(token: str):
        await q.put(token)

    # 4. Lancement de l'agent 
    async def run_agent():
        try:
            # Note la nouvelle méthode qu'on va créer : process_multimodal_chat
            await agent_runner.process_multimodal_chat(prompt, image_b64,image_path_db, real_session_id, stream_callback)
        except Exception as e:
            print(f"❌ Erreur Agent Multimodal : {e}")
        finally:
            await q.put(None)

    asyncio.create_task(run_agent())

    async def stream_generator():
        while True:
            token = await q.get()
            if token is None: 
                break
            yield token

    # 5. Headers pour le proxy SvelteKit
    headers = {
        "x-session-id": str(real_session_id),
        # IMPORTANT : Force le modèle visuel ici si ton modèle par défaut n'est pas multimodal !
        "x-chosen-model": "qwen3-vl:8b" 
    }

    return StreamingResponse(stream_generator(), media_type="text/plain", headers=headers)
