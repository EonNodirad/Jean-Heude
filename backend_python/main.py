from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
import os
import httpx
import memory
import aiosqlite
import re
import asyncio
from dotenv import load_dotenv
from contextlib import asynccontextmanager
load_dotenv()
STT_SERVER_URL = os.getenv("STT_SERVER_URL")
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- PHASE DE DÉMARRAGE ---
    print("🚀 Initialisation de Jean-Heude...")
    async with aiosqlite.connect("memory/memoire.db") as db:
        await db.execute("CREATE TABLE IF NOT EXISTS memory_chat (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, timestamp TIMESTAMP, sessionID INTEGER)")
        await db.execute("CREATE TABLE IF NOT EXISTS historique_chat (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TIMESTAMP, resume TEXT, userID TEXT)")
        await db.commit()
    await memory.get_tools()  
    memory.get_memory()
    print("✅ Jean-Heude est prêt !")
    asyncio.create_task(memory.cleanup_audio_store())
    yield
    # --- PHASE DE FERMETURE ---
    print("💤 Extinction...")

# Au début de main.py
# Dans ton fichier principal


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
        cursor = await db.execute( 
            "SELECT role, content FROM memory_chat WHERE sessionID = ? ORDER BY timestamp DESC LIMIT 10",
            (session_id,)
        )
        lignes= await cursor.fetchall()
        await db.commit()
        print(f"💾 Sauvegarde User : {text_content}")

        contexte_message = [{"role" : m[0], "content": m[1] }for m in reversed(lignes)]

    # 3. Sélection du modèle et génération
    chosen_model = await memory.decide_model(contexte_message)

    async def generate():
        assistant_final_text = ""
        async for chunk in memory.chat_with_memories(contexte_message, chosen_model):
            yield chunk
            clean_chunk = re.sub(r'\|\|AUDIO_ID:.*?\|\|', '', chunk)
            if not clean_chunk.startswith("¶"): # On garde ta logique pour les pensées
                assistant_final_text += clean_chunk
        
        # 4. Sauvegarde finale de la réponse assistant
        if assistant_final_text.strip():
            async with aiosqlite.connect("memory/memoire.db") as db_final:
                await db_final.execute(
                    "INSERT INTO memory_chat (role, content, timestamp, sessionID) VALUES (?, ?, datetime('now'), ?)",
                    ("assistant", assistant_final_text, session_id)
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
        
        # Optionnel : nettoyer le store ici ou via le cleanup global
            #memory.audio_store.pop(audio_id, None)

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
    return await run_jean_heude_logic(text_transcribed, session_id)
