
import os
from IA import Orchestrator
from mem0 import Memory 

from ollama import Client
from dotenv import load_dotenv


load_dotenv()
remote_host = os.getenv("URL_SERVER_OLLAMA")

orchestrator = Orchestrator()
client = Client(host=remote_host)

model = "phi3:mini"

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
            "host": "URL_QDRANT",
            "port": 6333,
            "embedding_model_dims": 768
        }
    }
}
#initit



_memory_instance = None
_list_models = None

def get_memory():
    """Initialise la mémoire seulement au premier appel"""
    global _memory_instance
    global _list_models
    if _memory_instance is None:
        _memory_instance = Memory.from_config(config)
    if _list_models is None:
        _list_models =orchestrator.get_local_models()
    return _memory_instance, _list_models

def chat_with_memories(message: str, user_id: str = "default_user") -> str:
    # Retrieve relevant memories
    mem, list_models = get_memory()
    print(list_models)
    #chosen_model = "llama3.1:8b"
    chosen_model = orchestrator.choose_model(message,list_models)
    print(chosen_model)
    if "embed" in chosen_model:
        chosen_model = "llama3.1:8b"
    print(f"--- Modèle sélectionné par Jean-Heude : {chosen_model} ---")

    print('debut mémoire')
    relevant_memories = mem.search(query=message, user_id=user_id, limit=3)
    print(relevant_memories)
    memories_str = ""
    if isinstance(relevant_memories, list):
        # Si c'est une liste, on boucle directement dedans
        memories_str = "\n".join(f"- {entry['memory']}" for entry in relevant_memories)
    elif isinstance(relevant_memories, dict) and "results" in relevant_memories:
        # Si c'est un dictionnaire avec une clé 'results'
        memories_str = "\n".join([f"- {m['memory']}" for m in relevant_memories["results"]])


    system_prompt = f"Tu es Jean-Heude, un assistant personnel. Ton but est d'être franc et réaliste pour donner la meilleure réponse possible, même si cela va à l'encontre de mon opinion.Tu réponds en format Markdown en te basant sur les requête et ta mémoire.\nUser Memories:\n{memories_str}"

    
    messages = [{"role": "system", "content": system_prompt},
            {"role": "user", "content": message}]
    print()
    # conversation
    try :

        response =  client.chat(model=chosen_model, stream=False,messages=messages)
        assistant_response = response.model_dump()['message']['content']


     # Create new memories from the conversation
        conversation = [
            {"role": "user", "content": message},
            {"role": "assistant", "content": assistant_response}]
        mem.add(conversation, user_id=user_id)

        return assistant_response
    except Exception as e :
        return f"Erreur de conexion à l'IA : {str(e)}"
