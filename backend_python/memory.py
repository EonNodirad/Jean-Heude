
import os
from IA import Orchestrator
from mem0 import Memory 
from typing import AsyncGenerator, Any
import tools
from ollama import AsyncClient
from dotenv import load_dotenv
import uuid
import asyncio

from tts_service import TTSService
audio_store ={}
tts = TTSService()
load_dotenv()
remote_host = os.getenv("URL_SERVER_OLLAMA")
url_qdrant = os.getenv("URL_QDRANT")

orchestrator = Orchestrator()
client = AsyncClient(host=remote_host)

model = "phi3:mini"
    
_available_tools = None

async def get_tools():
    global _available_tools
    if _available_tools is None:
        print("--- Chargement initial des outils... ---")
        _available_tools = await tools.get_all_tools()
    return _available_tools

config = {
    "telemetry": False,
    "llm": {
        "provider": "ollama",
        "config": {
            "model":model,
            "ollama_base_url": remote_host,
            "temperature":0.1
        }
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "model":"nomic-embed-text",
            "openai_base_url": f"{remote_host}/v1",
            "api_key": "ollama",
            "embedding_dims": 768
        }
    },
    "vector_store": {
        "provider":"qdrant",
        "config":{
            "host": url_qdrant,
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
    if _memory_instance is None:
        _memory_instance = Memory.from_config(config)
    return _memory_instance

def decide_model(message:str):
    global _list_models
    if _list_models is None:
        raw_models =orchestrator.get_local_models()
        print  (_list_models)
        blacklist = ["embed", "classification", "rerank","vision","mini","llama"]
        _list_models =[
            m for m in raw_models
            if not any(word in m.lower()for word in blacklist)
        ]
        print(f"--- Modèles de chat autorisés : {_list_models} ---")
    chosen_model = orchestrator.choose_model(message,_list_models)
    print(chosen_model)
    if "embed" in chosen_model:
        chosen_model = "llama3.1:8b"
    print(f"--- Modèle sélectionné par Jean-Heude : {chosen_model} ---")
    return chosen_model

async def pre_generate_audio(audio_id, text):
    try:
        loop = asyncio.get_running_loop()
        # On exécute la génération lourde dans un thread séparé pour ne pas bloquer le chat
        audio_data = await loop.run_in_executor(None, tts.generate_wav, text)
        audio_store[audio_id] = audio_data
        print(f"✅ Audio {audio_id} prêt")
    except Exception as e:
        print(f"Erreur pré-génération TTS: {e}")
        
async def chat_with_memories(message: str, chosen_model: str, user_id: str = "default_user") -> AsyncGenerator[str,Any]:
    # 1. Initialisation et récupération de la mémoire
    print("début mémoire")
    mem = get_memory()
    relevant_memories = mem.search(query=message, user_id=user_id, limit=3)
    
    # Formatage de la mémoire
    memories_str = ""
    if isinstance(relevant_memories, list):
        memories_str = "\n".join(f"- {entry['memory']}" for entry in relevant_memories)
    elif isinstance(relevant_memories, dict) and "results" in relevant_memories:
        memories_str = "\n".join([f"- {m['memory']}" for m in relevant_memories["results"]])
    print("fin de mémoire...")
    system_prompt = (
    f"Tu es Jean-Heude, un assistant personnel franc et qui donne un avis objectif même si pas en accord avec l'utilisateur\n"
    "Tu répondra en format markdown"
    "limite ta pensée au strict minimum. Ne boucle pas si un outil donne une "
    "réponse claire. Sois efficace."
    f"\nUser Memories:\n{memories_str}"
)
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message}
    ]
    assistant_response =""
    total_assistant_content = ""
    buffer_audio = ""
    # 2. Récupération des outils MCP dynamiques
    # On le fait à chaque appel pour être sûr d'avoir les outils à jour
    available_tools = await get_tools()
    print("tools ok")
    # -----------------------------------------------------------------------
    try:
        print("début de boucle")
        while True:
            stream = await client.chat(
            model='qwen3:8b',
            messages=messages,
            tools=available_tools,
            stream=True,
            think = True,

            )

            thinking = ''
            content = ''
            tool_calls = []

            done_thinking = False
            # accumulate the partial fields
            async for chunk in stream:
                if chunk.message.thinking:
                    thinking += chunk.message.thinking
                    yield f"¶{chunk.message.thinking}"
                if chunk.message.content:
                    if not done_thinking:
                        done_thinking = True
                    total_assistant_content += chunk.message.content
                    assistant_response+= chunk.message.content
                    yield chunk.message.content
                    content += chunk.message.content
                #--------------------------------logic TTS
                    buffer_audio += chunk.message.content
                    if any(p in chunk.message.content for p in [".", "!", "?", "\n", ";"]) and len(buffer_audio) > 10:
                        audio_id = str(uuid.uuid4())
                        phrase_a_lire = buffer_audio.strip()
                        
                        # LANCEMENT EN ARRIÈRE-PLAN (Non-bloquant)
                        asyncio.create_task(pre_generate_audio(audio_id, phrase_a_lire))
                        
                        # On envoie le signal à Svelte
                        yield f"||AUDIO_ID:{audio_id}||"
                        
                        buffer_audio = "" # Reset le buffer


                if chunk.message.tool_calls:
                    tool_calls.extend(chunk.message.tool_calls)
                    print(chunk.message.tool_calls)
                    await asyncio.sleep(0.01)

  # append accumulated fields to the messages
            if thinking or content or tool_calls:
                messages.append({'role': 'assistant', 'thinking': thinking, 'content': content, 'tool_calls': tool_calls})

            if not tool_calls:
                break
            for call in tool_calls:
                status_text = f"Je vais utiliser l'outil : {call.function.name}..."
                yield f"\n*{status_text}.*\n"
                yield "\n"
                
                status_audio_id = str(uuid.uuid4())
                asyncio.create_task(pre_generate_audio(status_audio_id, status_text))
                yield f"||AUDIO_ID:{status_audio_id}||"
                # Exécution
                result = await tools.call_tool_execution(call.function.name, call.function.arguments)

                # On ajoute le résultat au contexte pour le tour suivant
                messages.append({
                    'role': 'tool',
                    'name': call.function.name,
                    'content': str(result),
                    'tool_call_id': getattr(call, 'id', 'call_' + call.function.name)
                })
        # 7. SAUVEGARDE EN MÉMOIRE
        if assistant_response.strip():
            conversation = [
                {"role": "user", "content": message},
                {"role": "assistant", "content": assistant_response}
            ]
            mem.add(conversation, user_id=user_id)


        if buffer_audio.strip():
                audio_id = str(uuid.uuid4())
                asyncio.create_task(pre_generate_audio(audio_id, buffer_audio.strip()))
                yield f"||AUDIO_ID:{audio_id}||"
                buffer_audio = ""
    except Exception as e:
        error_msg = f"Erreur Jean-Heude : {str(e)}"
        print(f"DEBUG ERROR: {error_msg}")
        yield error_msg
