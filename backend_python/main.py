from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException, Depends, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
import re as _re
from urllib.parse import urlparse
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
from collections import defaultdict, deque
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

# --- Buffer circulaire pour les logs admin ---
class _DequeHandler(logging.Handler):
    def __init__(self, maxlen: int = 500):
        super().__init__()
        self.records: deque[dict] = deque(maxlen=maxlen)
        self._subscribers: list[asyncio.Queue] = []

    def emit(self, record: logging.LogRecord):
        import datetime as _dt
        entry = {
            "time": _dt.datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S"),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        self.records.append(entry)
        for q in list(self._subscribers):
            try:
                q.put_nowait(entry)
            except Exception:
                pass

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

_log_handler = _DequeHandler(maxlen=500)
_log_handler.setLevel(logging.DEBUG)
logging.getLogger().addHandler(_log_handler)

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
from auth import (  # noqa: E402
    init_auth_db, create_global_account, verify_password,
    create_access_token, decode_access_token, revoke_token,
    generate_link_code, set_admin, ban_user, delete_user, list_users,
)

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
# allow_credentials=True est incompatible avec ["*"] (spec CORS) — on désactive dans ce cas
_CORS_CREDENTIALS = ALLOWED_ORIGINS != ["*"]

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
    allow_credentials=_CORS_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 🔐 MODÈLES ET ROUTES D'AUTHENTIFICATION
# ==========================================
class AuthRequest(BaseModel):
    user_id: str
    password: str

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        if not _re.match(r'^[a-zA-Z0-9_-]{3,50}$', v):
            raise ValueError("user_id invalide : 3-50 caractères alphanumériques, _ ou - autorisés.")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Mot de passe trop court (minimum 6 caractères).")
        if len(v) > 256:
            raise ValueError("Mot de passe trop long.")
        return v

@app.post("/api/register")
async def register_user(req: AuthRequest, request: Request):
    _check_rate_limit(request.client.host if request.client else "unknown")
    success = create_global_account(req.user_id, req.password)
    if success:
        account = verify_password(req.user_id, req.password) or {}
        token = create_access_token({"user_id": req.user_id, "is_admin": account.get("is_admin", False)})
        return {"status": "success", "message": "Compte créé.", "access_token": token, "user_id": req.user_id, "is_admin": account.get("is_admin", False)}
    else:
        raise HTTPException(status_code=400, detail="Ce pseudo est déjà pris.")

@app.post("/api/login")
async def login_user(req: AuthRequest, request: Request):
    _check_rate_limit(request.client.host if request.client else "unknown")
    account = verify_password(req.user_id, req.password)
    if account:
        if account.get("is_admin") == -1:
            raise HTTPException(status_code=403, detail="Compte désactivé.")
        token = create_access_token({"user_id": req.user_id, "is_admin": account.get("is_admin", False)})
        return {"status": "success", "user_id": req.user_id, "access_token": token, "is_admin": account.get("is_admin", False)}
    else:
        raise HTTPException(status_code=401, detail="Identifiants incorrects.")

@app.post("/api/logout")
async def logout_user(authorization: str = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        revoke_token(token)
    return {"status": "success"}

@app.post("/api/generate-link-code")
async def generate_link_code_endpoint(user_id: str = Depends(get_current_user_dt)):
    """Génère un code OTP à 6 chiffres (TTL 10 min) pour lier Discord/Telegram."""
    code = generate_link_code(user_id)
    return {"code": code, "expires_in_seconds": 600}

# ==========================================
# 🛡️ ADMIN — Dépendance de rôle
# ==========================================
async def get_admin_user(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token manquant.")
    token = authorization.split(" ")[1]
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré.")
    if not payload.get("is_admin"):
        raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs.")
    return payload["user_id"]

# ==========================================
# 🛡️ ADMIN — Routes
# ==========================================
@app.get("/api/admin/users")
async def admin_list_users(_admin: str = Depends(get_admin_user)):
    return list_users()

@app.post("/api/admin/users/{target_id}/ban")
async def admin_ban_user(target_id: str, _admin: str = Depends(get_admin_user)):
    if not ban_user(target_id):
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    return {"ok": True}

@app.post("/api/admin/users/{target_id}/set-admin")
async def admin_set_admin(target_id: str, body: dict, _admin: str = Depends(get_admin_user)):
    set_admin(target_id, bool(body.get("is_admin", False)))
    return {"ok": True}

@app.delete("/api/admin/users/{target_id}")
async def admin_delete_user(target_id: str, admin: str = Depends(get_admin_user)):
    if target_id == admin:
        raise HTTPException(status_code=400, detail="Impossible de supprimer son propre compte.")
    if not delete_user(target_id):
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    return {"ok": True}

@app.get("/api/models")
async def list_models(_user: str = Depends(get_current_user_dt)):
    """Liste les modèles Ollama disponibles sur le serveur."""
    models_list = await memory.orchestrator.get_local_models()
    return {"models": models_list}

@app.get("/api/admin/stats")
async def admin_stats(hours: int = 24, _admin: str = Depends(get_admin_user)):
    metrics = await memory_manager.sqlite.get_metrics_summary(hours)
    active_sessions = await memory_manager.sqlite.get_active_sessions_count()
    return {"metrics_by_model": metrics, "active_sessions_last_hour": active_sessions, "window_hours": hours}

@app.get("/api/admin/health")
async def admin_health(_admin: str = Depends(get_admin_user)):
    return await health_check()

@app.get("/api/admin/sessions")
async def admin_sessions(limit: int = 100, _admin: str = Depends(get_admin_user)):
    rows = await memory_manager.sqlite.get_all_sessions(limit)
    return rows

@app.post("/api/admin/broadcast")
async def admin_broadcast(body: dict, _admin: str = Depends(get_admin_user)):
    message = body.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message vide.")
    await gateway.broadcast_system_message(message)
    return {"ok": True, "sent_to": len(gateway.active_connections)}

@app.get("/api/admin/mcp-config")
async def admin_get_mcp_config(_admin: str = Depends(get_admin_user)):
    try:
        with open("mcp_servers.yaml", "r", encoding="utf-8") as f:
            return {"content": f.read()}
    except FileNotFoundError:
        return {"content": "mcp_servers:\n"}

@app.put("/api/admin/mcp-config")
async def admin_save_mcp_config(body: dict, _admin: str = Depends(get_admin_user)):
    import yaml as _yaml
    content = body.get("content", "")
    try:
        _yaml.safe_load(content)
    except _yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"YAML invalide : {e}")
    with open("mcp_servers.yaml", "w", encoding="utf-8") as f:
        f.write(content)
    return {"status": "ok"}

@app.get("/api/admin/logs")
async def admin_logs(limit: int = 100, level: str = "", _admin: str = Depends(get_admin_user)):
    entries = list(_log_handler.records)
    if level:
        entries = [e for e in entries if e["level"] == level.upper()]
    return entries[-limit:]

@app.websocket("/ws/admin/logs")
async def admin_logs_ws(websocket: WebSocket, token: str = Query(None)):
    if not token:
        await websocket.close(code=1008)
        return
    payload = decode_access_token(token)
    if not payload or not payload.get("is_admin"):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    q = _log_handler.subscribe()
    try:
        while True:
            try:
                entry = await asyncio.wait_for(q.get(), timeout=20)
                await websocket.send_json(entry)
            except asyncio.TimeoutError:
                await websocket.send_json({"ping": True})
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        _log_handler.unsubscribe(q)

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
    if len(audio_binary) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Fichier audio trop volumineux (max 10 MB).")
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
    user_id: str = Depends(get_current_user_dt)
):
    if len(prompt) > 16000:
        raise HTTPException(status_code=400, detail="Prompt trop long (max 16 000 caractères).")
    real_session_id = int(session_id) if session_id and session_id not in ('null', 'undefined') else None
    
    if not real_session_id:
         resume = "Analyse: " + prompt[:20] + "..."
         real_session_id = await memory_manager.create_session(user_id, resume)

    image_b64 = None
    image_path_db = None
    if image:
        contents = await image.read()
        if len(contents) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Image trop volumineuse (max 10 MB).")
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

# ==========================================
# 📁 ROUTES FICHIERS UTILISATEUR (Sécurisées Multi-Tenant)
# ==========================================

# ==========================================
# 🩺 HEALTH CHECK
# ==========================================
def _base_url(url: str) -> str:
    """Extrait scheme://host:port d'une URL complète."""
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"

async def _ping(url: str, any_response_ok: bool = False) -> str:
    """Tente un GET sur url.
    - any_response_ok=True : toute réponse HTTP = service up (pour les services sans /health)
    - any_response_ok=False : seulement 200 = ok
    """
    try:
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get(url)
            if any_response_ok or r.status_code == 200:
                return "ok"
            return f"degraded ({r.status_code})"
    except Exception:
        return "unreachable"

@app.get("/health")
async def health_check():
    """Vérifie l'état de chaque dépendance."""
    status: dict = {}

    # Ollama
    status["ollama"] = await _ping(memory.remote_host)

    # Qdrant — URL_QDRANT peut être "localhost" ou "http://localhost:6333"
    raw_qdrant = os.getenv("URL_QDRANT", "http://localhost:6333")
    if not raw_qdrant.startswith("http"):
        raw_qdrant = f"http://{raw_qdrant}:6333"
    status["qdrant"] = await _ping(f"{raw_qdrant}/healthz")

    # TTS — pas de /health, on ping la racine (tout retour HTTP = service up)
    tts_url = os.getenv("TTS_SERVER_URL", "")
    if tts_url:
        status["tts"] = await _ping(_base_url(tts_url), any_response_ok=True)
    else:
        status["tts"] = "not_configured"

    # STT — idem
    if STT_SERVER_URL:
        status["stt"] = await _ping(_base_url(STT_SERVER_URL), any_response_ok=True)
    else:
        status["stt"] = "not_configured"

    # Neo4j — browser HTTP sur port 7474
    neo4j_uri = os.getenv("NEO4J_URI", "")
    if neo4j_uri:
        # bolt://host:7687 → http://host:7474
        parsed = urlparse(neo4j_uri)
        neo4j_http = f"http://{parsed.hostname}:7474"
        status["neo4j"] = await _ping(neo4j_http, any_response_ok=True)
    else:
        status["neo4j"] = "not_configured"

    overall = "ok" if all(v == "ok" for v in status.values()) else "degraded"
    return {"status": overall, "services": status}

@app.get("/api/files")
async def list_files(user_id: str = Depends(get_current_user_dt)):
    """Liste tous les fichiers et dossiers de l'utilisateur connecté."""
    return memory_manager.list_user_files(user_id)

@app.get("/api/files/{path:path}")
async def read_file(path: str, user_id: str = Depends(get_current_user_dt)):
    """Retourne le contenu d'un fichier de l'utilisateur."""
    try:
        content = memory_manager.read_user_file(user_id, path)
        return {"path": path, "content": content}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Fichier introuvable.")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Accès refusé.")

@app.put("/api/files/{path:path}")
async def write_file(path: str, body: dict, user_id: str = Depends(get_current_user_dt)):
    """Met à jour le contenu d'un fichier de l'utilisateur."""
    content = body.get("content", "")
    try:
        memory_manager.write_user_file(user_id, path, content)
        return {"ok": True}
    except PermissionError:
        raise HTTPException(status_code=403, detail="Accès refusé.")

@app.post("/api/files/{path:path}")
async def create_file(path: str, user_id: str = Depends(get_current_user_dt)):
    """Crée un nouveau fichier vide pour l'utilisateur."""
    try:
        memory_manager.create_user_file(user_id, path)
        return {"ok": True}
    except FileExistsError:
        raise HTTPException(status_code=409, detail="Le fichier existe déjà.")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Accès refusé.")

@app.delete("/api/files/{path:path}")
async def delete_file(path: str, user_id: str = Depends(get_current_user_dt)):
    """Supprime un fichier de l'utilisateur."""
    try:
        memory_manager.delete_user_file(user_id, path)
        return {"ok": True}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Fichier introuvable.")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Accès refusé.")