
import os

from mem0 import Memory 

from ollama import Client
from dotenv import load_dotenv


load_dotenv()
remote_host = os.getenv("URL_SERVER_OLLAMA")
appelle_IA = os.getenv("APPELLE_SERVER_OLLAMA")

client = Client(host=remote_host)

model = "llama3.1:8b"

config = {
    "llm": {
        "provider": "ollama",
        "config": {
            "model":model,
            "ollama_base_url": remote_host,
            "temperature":0.1
        }
    },
    "embedder": {
        "provider": "ollama",
        "config": {
            "model":"nomic-embed-text",
            "ollama_base_url": remote_host,
            "embedding_dims": 768
        }
    },
    "vector_store": {
        "provider":"qdrant",
        "config":{
            "host": "localhost",
            "port": 6333,
            "embedding_model_dims": 768
        }
    }
}
#initit
memory =Memory.from_config(config)


def chat_with_memories(message: str, user_id: str = "default_user") -> str:
    # Retrieve relevant memories
    relevant_memories = memory.search(query=message, user_id=user_id, limit=3)
    

    memories_str = ""
    if isinstance(relevant_memories, list):
        # Si c'est une liste, on boucle directement dedans
        memories_str = "\n".join(f"- {entry['memory']}" for entry in relevant_memories)
    elif isinstance(relevant_memories, dict) and "results" in relevant_memories:
        # Si c'est un dictionnaire avec une clé 'results'
        memories_str = "\n".join([f"- {m['memory']}" for m in relevant_memories["results"]])


    system_prompt = f"Tu es Jean-Heude un assistant personnelle. Ton but est d'être franc et réaliste pour donner la meilleure réponse possible même si c'est contre le miens. Tu réponds en format Markdown en te basant sur les requête et ta mémoire.\nUser Memories:\n{memories_str}"

    
    messages = [{"role": "system", "content": system_prompt},
            {"role": "user", "content": message}]

    # conversation
    try :
        #response = requests.post(appelle_IA, json= payload)
        response =  client.chat(model="llama3.1:8b", stream=False,messages=messages)
        assistant_response = response.model_dump()['message']['content']


     # Create new memories from the conversation
        conversation = [
            {"role": "user", "content": message},
            {"role": "assistant", "content": assistant_response}]
        memory.add(conversation, user_id=user_id)

        return assistant_response
    except Exception as e :
        return f"Erreur de conexion à l'IA : {str(e)}"
