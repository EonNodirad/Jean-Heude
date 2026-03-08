from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from PIL import Image
from fastapi.staticfiles import StaticFiles
import os
import httpx
from gateway import Gateway
from agent_runner import AgentRunner
import memory_IA as memory
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

# ✅ IMPORT DE L'AUTHENTIFICATION
from auth import init_auth_db, create_global_account, verify_password

load_dotenv()
STT_SERVER_URL = os.getenv("STT_SERVER_URL", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "*")

async def watch_tools_changes():
    print("👀 [Auto-Watch] Surveillance JIT (Skills & MCP) activée...")
    if not os.path.exists("skills"):
        os.makedirs("skills")
    if not os.path.exists("mcp_servers.yaml"):
        with open("mcp_servers.yaml", "w", encoding="utf-8") as f:
            f.write("mcp_servers:\n")
            
    async for changes in awatch("skills", "mcp_servers.yaml"):
        print(f"🔄 [Auto-Watch] Modification détectée : {changes}. Mise à jour...")
        await tools.sync_skills_to_qdrant()

# ==========================================
# 🛡️ GARDE-FRONTIÈRE BDD UTILISATEURS
# ==========================================
async def get_and_init_user_db(user_id: str) -> str:
    """Retourne le chemin de la BDD de l'utilisateur et s'assure qu'elle est à jour."""
    db_path = f"memory/users/{user_id}/memoire.db"
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS historique_chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            timestamp TIMESTAMP, 
            resume TEXT, 
            userID TEXT
        )""")
        
        await db.execute("""CREATE TABLE IF NOT EXISTS memory_chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            role TEXT, 
            content TEXT, 
            timestamp TIMESTAMP, 
            sessionID INTEGER,
            image TEXT
        )""")
        
        await db.execute("""CREATE TABLE IF NOT EXISTS long_term_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chunk_text TEXT,
            vector_id TEXT
        )""")
        
        try:
            await db.execute("ALTER TABLE memory_chat ADD COLUMN image TEXT")
        except Exception:
            pass
            
        await db.commit()
        
    return db_path

# ==========================================
# 🚀 LIFESPAN (Démarrage du serveur)
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Initialisation de Jean-Heude...")
    
    # 1. Base d'authentification globale
    init_auth_db()

    # 2. Collection vectorielle globale
    try:
        await memory.client_qdrant.get_collection("jean_heude_memories")
    except Exception:
        print("📦 Création de la collection Qdrant 'jean_heude_memories'...")
        await memory.client_qdrant.create_collection(
            collection_name="jean_heude_memories",
            vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
        )

    # 3. Synchronisation par utilisateur
    users_dir = "memory/users"
    if os.path.exists(users_dir):
        for user_folder in os.listdir(users_dir):
            if os.path.isdir(os.path.join(users_dir, user_folder)):
                print(f"🔄 Initialisation de la base de données pour : {user_folder}...")
                await get_and_init_user_db(user_folder)
                print(f"📖 Synchro de la mémoire Markdown pour : {user_folder}...")
                await memory.sync_memory_md(user_folder)
                
    # 4. Chargement des Outils
    await tools.sync_skills_to_qdrant()
    
    print("✅ Jean-Heude est prêt !")
    asyncio.create_task(memory.cleanup_audio_store())
    asyncio.create_task(watch_tools_changes())
    yield
    print("💤 Extinction...")

# ==========================================
# ⚙️ INITIALISATION FASTAPI
# ==========================================
if not os.path.exists("memory/users"):
    os.makedirs("memory/users")

app = FastAPI(lifespan=lifespan)
agent_runner = AgentRunner()
gateway = Gateway(agent_runner)

# 🎯 MONTAGE STATIQUE ISOLÉ PAR UTILISATEUR
app.mount("/api/users", StaticFiles(directory="memory/users"), name="users_media")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 🔐 MODÈLES ET ROUTES D'AUTHENTIFICATION
# ==========================================
class AuthRequest(BaseModel):
    user_id: str
    password: str

@app.post("/api/register")
async def register_user(req: AuthRequest):
    success = create_global_account(req.user_id, req.password)
    if success:
        return {"status": "success", "message": "Compte créé."}
    else:
        raise HTTPException(status_code=400, detail="Ce pseudo est déjà pris.")

@app.post("/api/login")
async def login_user(req: AuthRequest):
    if verify_password(req.user_id, req.password):
        return {"status": "success", "user_id": req.user_id}
    else:
        raise HTTPException(status_code=401, detail="Identifiants incorrects.")

# ==========================================
# 🔌 WEBSOCKET
# ==========================================
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await gateway.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_json()
            
            if isinstance(data, dict) and not data.get("user_id"):
                await websocket.send_json({"type": "error", "content": "Non autorisé. Veuillez vous reconnecter."})
                continue
                
            await gateway.handle_event(client_id, data)
    except WebSocketDisconnect:
        gateway.disconnect(client_id)

# ==========================================
# 🗃️ ROUTES HISTORIQUE
# ==========================================
@app.get("/history")
async def get_historique_list(user_id: str):
    db_path = await get_and_init_user_db(user_id)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id, resume, timestamp FROM historique_chat ORDER BY timestamp DESC")
        lignes = await cursor.fetchall()
        return [{"id": ligne["id"], "resume": ligne["resume"], "timestamp": ligne["timestamp"]} for ligne in lignes]

@app.get("/history/{session_id}")
async def get_history(session_id: int, user_id: str):
    db_path = await get_and_init_user_db(user_id)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT role, content, image FROM memory_chat WHERE sessionID = ? ORDER BY timestamp ASC",
            (session_id,)
        )
        lignes = await cursor.fetchall()
        return [{"role": ligne["role"], "content": ligne["content"], "image": ligne["image"]} for ligne in lignes]

# ==========================================
# 🎤 ROUTE STT
# ==========================================
@app.post("/stt")
async def voice_endpoint(
    file: UploadFile = File(...), 
    session_id: str | None = Form(None),
    user_id: str = Form(...) 
):
    audio_binary = await file.read()
    text_transcribed = ""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {'file': ('audio.wav', audio_binary, 'audio/wav')}
            response = await client.post(STT_SERVER_URL, files=files)
            if response.status_code == 200:
                data = response.json()
                text_transcribed = data.get("text", "")
    except Exception as e:
        print(f"❌ Erreur STT : {e}")
        return {"error": "Serveur STT injoignable"}

    if not text_transcribed:
        return {"error": "Aucune parole détectée"}

    if session_id is None or session_id in ('null', 'undefined'):
        db_path = await get_and_init_user_db(user_id)
        async with aiosqlite.connect(db_path) as db:
            resume = text_transcribed[:30] + "..."
            cursor = await db.execute(
                "INSERT INTO historique_chat (timestamp, resume, userID) VALUES (datetime('now'), ?, ?)",
                (resume, user_id) 
            )
            await db.commit()
            real_session_id = cursor.lastrowid
    else:
        real_session_id = int(session_id)

    q = asyncio.Queue()

    async def stream_callback(token: str):
        await q.put(token)

    async def run_agent():
        try:
            await agent_runner.process_chat(text_transcribed, real_session_id, user_id, stream_callback)
        except Exception as e:
            print(f"❌ Erreur Agent : {e}")
        finally:
            await q.put(None)

    asyncio.create_task(run_agent())

    async def stream_generator():
        while True:
            token = await q.get()
            if token is None:
                break
            yield token

    headers = {"x-session-id": str(real_session_id), "x-chosen-model": "qwen3:8b"}
    return StreamingResponse(stream_generator(), media_type="text/plain", headers=headers)

# ==========================================
# 🖼️ ROUTE MULTIMODAL
# ==========================================
@app.post("/api/multimodal")
async def multimodal_endpoint(
    prompt: str = Form(...),
    image: UploadFile | None = File(None),
    session_id: str | None = Form(None),
    user_id: str = Form(...) 
):
    real_session_id = int(session_id) if session_id and session_id not in ('null', 'undefined') else None
    
    if not real_session_id:
        db_path = await get_and_init_user_db(user_id)
        async with aiosqlite.connect(db_path) as db:
            resume = "Analyse: " + prompt[:20] + "..."
            cursor = await db.execute(
                "INSERT INTO historique_chat (timestamp, resume, userID) VALUES (datetime('now'), ?, ?)",
                (resume, user_id)
            )
            await db.commit()
            real_session_id = cursor.lastrowid

    image_b64 = None
    image_path_db = None
    if image:
        contents = await image.read()
        image_b64 = base64.b64encode(contents).decode('utf-8')
        try:
            img_pil = Image.open(io.BytesIO(contents))
            img_pil.thumbnail((800, 800)) 
            filename = f"{uuid.uuid4()}.jpg"
            
            # 🎯 DOSSIER D'UPLOAD ISOLÉ PAR UTILISATEUR
            user_uploads_dir = f"memory/users/{user_id}/uploads"
            os.makedirs(user_uploads_dir, exist_ok=True)
            filepath = f"{user_uploads_dir}/{filename}"
            
            img_pil.convert("RGB").save(filepath, "JPEG", quality=70)
            
            # 🎯 CHEMIN D'ACCÈS POUR LE FRONTEND
            image_path_db = f"/api/users/{user_id}/uploads/{filename}"
            
        except Exception as e:
            print(f"❌ Erreur de sauvegarde image : {e}")

    q = asyncio.Queue()
    async def stream_callback(token: str):
        await q.put(token)

    async def run_agent():
        try:
            await agent_runner.process_multimodal_chat(prompt, image_b64, image_path_db, real_session_id, user_id, stream_callback)
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

    headers = {"x-session-id": str(real_session_id), "x-chosen-model": "qwen3-vl:8b"}
    return StreamingResponse(stream_generator(), media_type="text/plain", headers=headers)

# ==========================================
# 🎵 ROUTE TTS
# ==========================================
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
                while chunk_index < len(entry["chunks"]):
                    yield entry["chunks"][chunk_index]
                    chunk_index += 1
            
                if entry["status"] == "done" and chunk_index >= len(entry["chunks"]):
                    break
                await asyncio.sleep(0.01)

        return StreamingResponse(chunk_generator(), media_type="application/octet-stream")
    except asyncio.TimeoutError:
        return {"error": "Le TTS est trop lent."}, 504