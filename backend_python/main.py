from fastapi import FastAPI
from pydantic import BaseModel
import IA
import sqlite3
import datetime
import memory
app = FastAPI()

class ChatInput(BaseModel):
    content : str
    session_id: int | None

connection = sqlite3.connect("../memory/memoire.db")
cursor = connection.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS memory_chat (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, timestamp TIMESTAMP, sessionID INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS historique_chat (id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp TIMESTAMP,resume TEXT,userID TEXT)")
# chaque discussion relié à un user ID et dans chaque discussion il y a ses message d'enregistrer sessionID = id de historique


@app.post("/chat")

async def chat_endpoint(input_data : ChatInput):

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
    # Jean-heude réfléchit
    response =memory.chat_with_memories(input_data.content)
    print(f"message reçu de Sveltekit : {input_data.content}")
    
    cursor.execute(
            "INSERT INTO memory_chat (role, content, timestamp, sessionID) VALUES (?, ?, datetime('now'), ?)",
            ("user", input_data.content, session_id)
        )
    connection.commit()
    print("sauvegard ", input_data.content)
    cursor.execute(
            "INSERT INTO memory_chat (role, content, timestamp, sessionID) VALUES (?, ?, datetime('now'), ?)",
            ("assistant", response, session_id)
        )
    connection.commit()
    print("sauvegarde ", response)
    return { "response": response,"session_id":session_id}
@app.get("/history")
async def get_historique_list():
    cursor.execute("SELECT id,resume,timestamp FROM historique_chat ORDER BY timestamp DESC")
    ligne = cursor.fetchall()
    return [{"id":l[0],"resume":l[1], "timestamp":l[2]} for l in ligne]

@app.get("/history/{session_id}")
async def get_history(session_id: int) :
    cursor.execute("SELECT role,content FROM memory_chat WHERE sessionID = ? ORDER BY timestamp ASC ",(session_id,))
    print(session_id)
    message = cursor.fetchall()
    return [{"role":m[0] , "content":m[1]} for m in message]
