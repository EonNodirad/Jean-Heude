from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
import sqlite3
import os
import memory

# Au début de main.py
if not os.path.exists("memory"):
    os.makedirs("memory")

app = FastAPI()

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
    cursor = connection.cursor()
    session_id = input_data.session_id
    print(session_id)
    if session_id is None:
        resume = input_data.content[:30] + "..." 
        cursor.execute(
            "INSERT INTO historique_chat (timestamp,resume,userID) VALUES (datetime('now'),?,?)",(resume,"noe_01")
        )
        connection.commit()
        session_id = cursor.lastrowid
        print(f"Nouvelle session créée : ID {session_id}")


    cursor.execute(
            "INSERT INTO memory_chat (role, content, timestamp, sessionID) VALUES (?, ?, datetime('now'), ?)",
            ("user", input_data.content, session_id)
     )
    connection.commit()
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
            else: full_text += chunk
            # sauvegarde dans historique
        cursor = connection.cursor()

        print("sauvegard ", input_data.content)
        cursor.execute(
            "INSERT INTO memory_chat (role, content, timestamp, sessionID) VALUES (?, ?, datetime('now'), ?)",
            ("assistant", full_text, session_id)
         )
        connection.commit()
        print("sauvegarde ", full_text)

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
