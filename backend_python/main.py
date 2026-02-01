from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
import sqlite3
import os
import memory
import aiosqlite
import io
import asyncio
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- PHASE DE DÉMARRAGE ---
    print("🚀 Initialisation de Jean-Heude...")
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

connection = sqlite3.connect("memory/memoire.db", check_same_thread=False)
cursorstart = connection.cursor()

cursorstart.execute("CREATE TABLE IF NOT EXISTS memory_chat (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, timestamp TIMESTAMP, sessionID INTEGER)")
cursorstart.execute("CREATE TABLE IF NOT EXISTS historique_chat (id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp TIMESTAMP,resume TEXT,userID TEXT)")
# chaque discussion relié à un user ID et dans chaque discussion il y a ses message d'enregistrer sessionID = id de historique


@app.post("/chat")
#appele l'IA
async def chat_endpoint(input_data : ChatInput):
    async with aiosqlite.connect("memory/memoire.db") as db :
        session_id = input_data.session_id
        if session_id is None:
            resume = input_data.content[:30] + "..." 
            cursor= await db.execute(
            "INSERT INTO historique_chat (timestamp,resume,userID) VALUES (datetime('now'),?,?)",(resume,"noe_01")
            )
            session_id = cursor.lastrowid
            print(f"Nouvelle session créée : ID {session_id}")


        await db.execute(
            "INSERT INTO memory_chat (role, content, timestamp, sessionID) VALUES (?, ?, datetime('now'), ?)",
            ("user", input_data.content, session_id)
        )
        print(f"sauvegarde :{input_data.content}")
        await db.commit()
    # selection model
        chosen_model = memory.decide_model(input_data.content)
    # Jean-heude réfléchit
        async def generate():
            full_text =""
            async for chunk in memory.chat_with_memories(input_data.content, chosen_model):
                yield chunk
        
                if "¶" in chunk:
            # C'est de la pensée, on ne l'ajoute PAS à full_text
            # On pourrait faire : current_thinking += chunk.replace("¶", "")
                    pass 
                else:
                    full_text += chunk
            # sauvegarde dans historique

            if full_text.strip():
                async with aiosqlite.connect("memory/memoire.db") as db_final:
                    await db_final.execute(
                        "INSERT INTO memory_chat (role, content, timestamp, sessionID) VALUES (?, ?, datetime('now'), ?)",
                        ("assistant", full_text, session_id)
                    )
                    await db_final.commit()
                    print("✅ Réponse complète sauvegardée en une seule fois.")
        return StreamingResponse(generate(), media_type="text/plain", headers={"X-Session-Id": str(session_id), "X-Chosen-Model": chosen_model})


@app.get("/history")
async def get_historique_list():
    cursor = connection.cursor()
    cursor.execute("SELECT id,resume,timestamp FROM historique_chat ORDER BY timestamp DESC")
    lignes = cursor.fetchall()
    return [{"id":ligne[0],"resume":ligne[1], "timestamp":ligne[2]} for ligne in lignes]

@app.get("/history/{session_id}")
async def get_history(session_id: int) :
    cursor = connection.cursor()
    cursor.execute("SELECT role,content FROM memory_chat WHERE sessionID = ? ORDER BY timestamp ASC ",(session_id,))
    print(session_id)
    message = cursor.fetchall()
    return [{"role":m[0] , "content":m[1]} for m in message]


@app.get("/api/tts/{audio_id}")

async def get_tts(audio_id:str):
    for _ in range(30):
        if audio_id in memory.audio_store:
            data = memory.audio_store.pop(audio_id) # On récupère et on vide pour la mémoireS
            if isinstance(data, io.BytesIO):
                return StreamingResponse(data, media_type="audio/wav")
            return StreamingResponse(data, media_type="audio/wav")
        await asyncio.sleep(0.1)
    return {"error": "Not ready yet"}
