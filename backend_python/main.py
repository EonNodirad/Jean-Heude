from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException, Depends, Header, Query, Request
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

import asyncio
import logging
import time
from collections import defaultdict
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from database.memory_manager import memory_manager
from watchfiles import awatch
import tools
import base64
import io
import uuid

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("jean_heude")

# --- Rate limiting ---
_login_attempts: dict[str, list[float]] = defaultdict(list)
_RATE_WINDOW = 60   # secondes
_RATE_MAX = 5       # tentatives max par fenêtre

def _check_rate_limit(ip: str):
    now = time.time()
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < _RATE_WINDOW]
    if len(_login_attempts[ip]) >= _RATE_MAX:
        raise HTTPException(status_code=429, detail="Trop de tentatives. Réessayez dans 60 secondes.")
    _login_attempts[ip].append(now)

# ✅ IMPORT DE L'AUTHENTIFICATION
from auth import init_auth_db, create_global_account, verify_password, create_access_token, decode_access_token  # noqa: E402

async def get_current_user_dt(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token manquant ou invalide")
    token = authorization.split(" ")[1]
    payload = decode_access_token(token)
    if not payload or "user_id" not in payload:
        raise HTTPException(status_code=401, detail="Token expiré ou invalide")
    return payload["user_id"]

load_dotenv()
STT_SERVER_URL = os.getenv("STT_SERVER_URL", "")
_raw_origins = os.getenv("FRONTEND_URL", "")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()] or ["*"]

async def watch_tools_changes():
    logger.info("[Auto-Watch] Surveillance JIT (Skills & MCP) activée.")
    if not os.path.exists("skills"):
        os.makedirs("skills")
    if not os.path.exists("mcp_servers.yaml"):
        with open("mcp_servers.yaml", "w", encoding="utf-8") as f:
            f.write("mcp_servers:\n")
            
    async for changes in awatch("skills", "mcp_servers.yaml"):
        logger.info(f"[Auto-Watch] Modification détectée : {changes}. Mise à jour...")
        await tools.sync_skills_to_qdrant()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initialisation de Jean-Heude...")
    
    # ✅ Initialisation de la base d'authentification
    init_auth_db()
    
    await memory_manager.sqlite.init_db()

    # --- NOUVEAU: Check Rapide Ollama ---
    ollama_online = False
    try:
        async with httpx.AsyncClient(timeout=2.0) as http_client:
            res = await http_client.get(memory.remote_host)
            if res.status_code == 200:
                ollama_online = True
                logger.info("[Ollama] Serveur détecté en ligne.")
            else:
                logger.warning(f"[Ollama] Statut inattendu: {res.status_code}")
    except Exception as e:
        logger.warning(f"[Ollama] Injoignable au démarrage (L'IA sera désactivée). Erreur: {e}")

    if ollama_online:
        try:
            await memory_manager.qdrant.init_collection("jean_heude_memories")
        except Exception as e:
            logger.warning(f"Impossible d'initialiser Qdrant (Serveur hors ligne ?) : {e}")

        users_dir = "memory/users"
        if os.path.exists(users_dir):
            for user_folder in os.listdir(users_dir):
                if os.path.isdir(os.path.join(users_dir, user_folder)):
                    logger.info(f"Synchro de la mémoire pour l'utilisateur : {user_folder}...")
                    await memory.sync_memory_md(user_folder)
        await tools.sync_skills_to_qdrant()
        # Pré-calcul des ancres sémantiques pour éviter la latence au premier message
        logger.info("[Startup] Pré-calcul des ancres sémantiques...")
        try:
            await memory.orchestrator._get_anchor_embeddings()
        except Exception as e:
            logger.warning("[Startup] Pré-calcul des ancres échoué (non bloquant) : %s", e)
    else:
        logger.info("[Startup] Synchronisation mémoires et skills ignorée car Ollama est absent.")

    logger.info("Jean-Heude est prêt !")
    asyncio.create_task(memory.cleanup_audio_store())
    asyncio.create_task(watch_tools_changes())
    yield
    logger.info("Extinction...")

if not os.path.exists("memory"):
    os.makedirs("memory")

app = FastAPI(lifespan=lifespan)
agent_runner = AgentRunner()
gateway = Gateway(agent_runner)

os.makedirs("memory/uploads", exist_ok=True)
app.mount("/api/uploads", StaticFiles(directory="memory/uploads"), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
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
async def register_user(req: AuthRequest, request: Request):
    _check_rate_limit(request.client.host if request.client else "unknown")
    success = create_global_account(req.user_id, req.password)
    if success:
        token = create_access_token({"user_id": req.user_id})
        return {"status": "success", "message": "Compte créé.", "access_token": token, "user_id": req.user_id}
    else:
        raise HTTPException(status_code=400, detail="Ce pseudo est déjà pris.")

@app.post("/api/login")
async def login_user(req: AuthRequest, request: Request):
    _check_rate_limit(request.client.host if request.client else "unknown")
    if verify_password(req.user_id, req.password):
        token = create_access_token({"user_id": req.user_id})
        return {"status": "success", "user_id": req.user_id, "access_token": token}
    else:
        raise HTTPException(status_code=401, detail="Identifiants incorrects.")

# ==========================================
# 🔌 WEBSOCKET
# ==========================================
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str, token: str = Query(None)):
    if not token:
        await websocket.close(code=1008)
        return
    payload = decode_access_token(token)
    if not payload or payload.get("user_id") != client_id:
        await websocket.close(code=1008)
        return

    await gateway.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_json()
            
            # SÉCURITÉ WEBSOCKET : On s'assure que Svelte a envoyé le user_id
            if isinstance(data, dict) and not data.get("user_id"):
                await websocket.send_json({"type": "error", "content": "Non autorisé. Veuillez vous reconnecter."})
                continue
                
            await gateway.handle_event(client_id, data)
    except WebSocketDisconnect:
        gateway.disconnect(client_id)

# ==========================================
# 🗃️ ROUTES HISTORIQUE (Sécurisées Multi-Tenant)
# ==========================================
@app.get("/history")
async def get_historique_list(user_id: str = Depends(get_current_user_dt)):
    """Récupère l'historique UNIQUEMENT pour l'utilisateur connecté"""
    return await memory_manager.sqlite.get_history_list(user_id)

@app.get("/history/{session_id}")
async def get_history(session_id: int, user_id: str = Depends(get_current_user_dt)):
    if not await memory_manager.sqlite.check_session_owner(session_id, user_id):
        raise HTTPException(status_code=403, detail="Accès non autorisé à cette session.")
    return await memory_manager.sqlite.get_history(session_id)

# ==========================================
# 🎤 ROUTE STT
# ==========================================
@app.post("/stt")
async def voice_endpoint(
    file: UploadFile = File(...), 
    session_id: str | None = Form(None),
    user_id: str = Depends(get_current_user_dt) # 🎯 REQUIS !
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
        logger.error(f"Erreur STT : {e}")
        return {"error": "Serveur STT injoignable"}

    if not text_transcribed:
        return {"error": "Aucune parole détectée"}

    if session_id is None or session_id == 'null' or session_id == 'undefined':
        resume = text_transcribed[:30] + "..."
        real_session_id = await memory_manager.create_session(user_id, resume)
    else:
        real_session_id = int(session_id)

    q = asyncio.Queue()

    async def stream_callback(token: str):
        await q.put(token)

    async def run_agent():
        try:
            # 🎯 ON PASSE LE USER_ID À L'AGENT
            await agent_runner.process_chat(text_transcribed, real_session_id, user_id, stream_callback)
        except Exception as e:
            logger.error(f"Erreur Agent : {e}")
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
    user_id: str = Depends(get_current_user_dt) # 🎯 REQUIS !
):
    real_session_id = int(session_id) if session_id and session_id not in ('null', 'undefined') else None
    
    if not real_session_id:
         resume = "Analyse: " + prompt[:20] + "..."
         real_session_id = await memory_manager.create_session(user_id, resume)

    image_b64 = None
    image_path_db = None
    if image:
        contents = await image.read()
        image_b64 = base64.b64encode(contents).decode('utf-8')
        try:
            img_pil = Image.open(io.BytesIO(contents))
            img_pil.thumbnail((800, 800)) 
            filename = f"{uuid.uuid4()}.jpg"
            filepath = f"memory/uploads/{filename}"
            img_pil.convert("RGB").save(filepath, "JPEG", quality=70)
            image_path_db = f"/api/uploads/{filename}"
        except Exception as e:
            logger.error(f"Erreur de sauvegarde image : {e}")

    q = asyncio.Queue()
    async def stream_callback(token: str):
        await q.put(token)

    async def run_agent():
        try:
            # 🎯 ON PASSE LE USER_ID À L'AGENT MULTIMODAL
            await agent_runner.process_multimodal_chat(prompt, image_b64, image_path_db, real_session_id, user_id, stream_callback)
        except Exception as e:
            logger.error(f"Erreur Agent Multimodal : {e}")
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