from fastapi import FastAPI
from pydantic import BaseModel
import IA

app = FastAPI()

class ChatInput(BaseModel):
    content : str


@app.post("/chat")

async def chat_endpoint(input_data : ChatInput):
    # Jean-heude réfléchit
    chat_message =[IA.create_message(IA.system_message,'system')]
    chat_message.append(IA.create_message(input_data.content,'user'))

    print(f"message reçu de Sveltekit : {input_data.content}")
    response =IA.chat(chat_message)
    return { "response": response}
