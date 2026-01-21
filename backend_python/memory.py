
import os
import requests
from mem0 import Memory 
import IA

model = "phi3:mini"
config = {
    "llm": {
        "provider": "ollama",
        "config": {
            "model":model,
            "ollama_base_url": "http://192.168.1.49:11434",
            "temperature":0.1
        }
    },
    "embedder": {
        "provider": "ollama",
        "config": {
            "model":"nomic-embed-text",
            "ollama_base_url": "http://192.168.1.49:11434",
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


    system_prompt = f"You are a helpful AI named Jean-Heude. Answer the question based on query and memories.\nUser Memories:\n{memories_str}"



    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": message}]

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ],
        "stream": False
    }
    # conversation
    try :
        response = requests.post("http://192.168.1.49:11434/api/chat", json= payload)
        response.raise_for_status()
        assistant_response = response.json()['message']['content']


     # Create new memories from the conversation
        conversation = [
            {"role": "user", "content": message},
            {"role": "assistant", "content": assistant_response}]
        memory.add(conversation, user_id=user_id)

        return assistant_response
    except Exception as e :
        return f"Erreur de conexion à l'IA : {str(e)}"
