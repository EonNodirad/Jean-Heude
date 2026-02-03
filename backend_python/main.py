from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
import sqlite3
import os
import httpx
import memory
import aiosqlite
import io
import asyncio
from contextlib import asynccontextmanager

STT_SERVER_URL = "http://localhost:8001/transcribe"
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- PHASE DE DÉMARRAGE ---
    print("🚀 Initialisation de Jean-Heude...")
    async with aiosqlite.connect("memory/memoire.db") as db:
        await db.execute("CREATE TABLE IF NOT EXISTS memory_chat (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, timestamp TIMESTAMP, sessionID INTEGER)")
        await db.execute("CREATE TABLE IF NOT EXISTS historique_chat (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TIMESTAMP, resume TEXT, userID TEXT)")
        await db.commit()
    await memory.get_tools()     # On charge les outils en RAM
    memory.get_memory()
    print("✅ Jean-Heude est prêt !")
    yield
    # --- PHASE DE FERMETURE ---
    print("💤 Extinction...")

# Au début de main.py

if not os.path.exists("memory"):
    os.makedirs("memory")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], # L'URL de ton site Svelte
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
class ChatInput(BaseModel):
    content : str
    session_id: int | None


async def run_jean_heude_logic(text_content: str, session_id: int | None):
    async with aiosqlite.connect("memory/memoire.db") as db:
        # 1. Gestion de la session
        if session_id is None:
            resume = text_content[:30] + "..."
            cursor = await db.execute(
                "INSERT INTO historique_chat (timestamp, resume, userID) VALUES (datetime('now'), ?, ?)",
                (resume, "noe_01")
            )
            session_id = cursor.lastrowid
            print(f"🆕 Nouvelle session créée : ID {session_id}")

        # 2. Sauvegarde du message utilisateur
        await db.execute(
            "INSERT INTO memory_chat (role, content, timestamp, sessionID) VALUES (?, ?, datetime('now'), ?)",
            ("user", text_content, session_id)
        )
        await db.commit()
        print(f"💾 Sauvegarde User : {text_content}")

    # 3. Sélection du modèle et génération
    chosen_model = memory.decide_model(text_content)

    async def generate():
        full_text = ""
        async for chunk in memory.chat_with_memories(text_content, chosen_model):
            yield chunk
            if "¶" not in chunk: # On ignore les pensées pour la DB
                full_text += chunk
        
        # 4. Sauvegarde finale de la réponse assistant
        if full_text.strip():
            async with aiosqlite.connect("memory/memoire.db") as db_final:
                await db_final.execute(
                    "INSERT INTO memory_chat (role, content, timestamp, sessionID) VALUES (?, ?, datetime('now'), ?)",
                    ("assistant", full_text, session_id)
                )
                await db_final.commit()
                print("✅ Réponse assistant sauvegardée.")

    return StreamingResponse(
        generate(), 
        media_type="text/plain", 
        headers={
            "X-Session-Id": str(session_id), 
            "X-Chosen-Model": chosen_model
        }
    )

@app.post("/chat")
#appele l'IA
async def chat_endpoint(input_data : ChatInput):
    return await run_jean_heude_logic(input_data.content, input_data.session_id)
@app.get("/history")
async def get_historique_list():
    async with aiosqlite.connect("memory/memoire.db") as db:
        db.row_factory = aiosqlite.Row # Optionnel : pour accéder par nom de colonne
        async with db.execute("SELECT id, resume, timestamp FROM historique_chat ORDER BY timestamp DESC") as cursor:
            lignes = await cursor.fetchall()
            return [{"id": l[0], "resume": l[1], "timestamp": l[2]} for l in lignes]

@app.get("/history/{session_id}")
async def get_history(session_id: int):
    async with aiosqlite.connect("memory/memoire.db") as db:
        async with db.execute("SELECT role, content FROM memory_chat WHERE sessionID = ? ORDER BY timestamp ASC", (session_id,)) as cursor:
            messages = await cursor.fetchall()
            return [{"role": m[0], "content": m[1]} for m in messages]


@app.get("/api/tts/{audio_id}")

async def get_tts(audio_id:str):
    for _ in range(750):
        if audio_id in memory.audio_store:
            data = memory.audio_store.pop(audio_id) # On récupère et on vide pour la mémoireS
            data.seek(0)
            if isinstance(data, io.BytesIO):
                return StreamingResponse(data, media_type="audio/wav")
            return StreamingResponse(data, media_type="audio/wav")
        await asyncio.sleep(0.02)
    return {"error": "Not ready yet"}

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
    return await run_jean_heude_logic(text_transcribed, session_id)
