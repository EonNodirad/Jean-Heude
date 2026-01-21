from fastapi import FastAPI
from pydantic import BaseModel
import IA
import sqlite3
import datetime
import memory
app = FastAPI()

class ChatInput(BaseModel):
    content : str

connection = sqlite3.connect("memoire.db")
cursor = connection.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS memory_chat (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, timestamp TIMESTAMP, sessionID TEXT)")



@app.post("/chat")

async def chat_endpoint(input_data : ChatInput):
    # Jean-heude réfléchit
    response =memory.chat_with_memories(input_data.content)
    print(f"message reçu de Sveltekit : {input_data.content}")
    return { "response": response}
