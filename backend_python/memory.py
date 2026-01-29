
import os
from IA import Orchestrator
from mem0 import Memory 
from typing import AsyncGenerator, Any
import tools
from ollama import AsyncClient
from dotenv import load_dotenv


load_dotenv()
remote_host = os.getenv("URL_SERVER_OLLAMA")
url_qdrant = os.getenv("URL_QDRANT")

orchestrator = Orchestrator()
client = AsyncClient(host=remote_host)

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


async def chat_with_memories(message: str, chosen_model: str, user_id: str = "default_user") -> AsyncGenerator[str,Any]:
    # 1. Initialisation et récupération de la mémoire
    mem = get_memory()
    relevant_memories = mem.search(query=message, user_id=user_id, limit=3)
    
    # Formatage de la mémoire
    memories_str = ""
    if isinstance(relevant_memories, list):
        memories_str = "\n".join(f"- {entry['memory']}" for entry in relevant_memories)
    elif isinstance(relevant_memories, dict) and "results" in relevant_memories:
        memories_str = "\n".join([f"- {m['memory']}" for m in relevant_memories["results"]])

    system_prompt = (
    f"Tu es Jean-Heude, un assistant personnel franc et qui donne un avis objectif même si pas en accord avec l'utilisateur\n"
    "Tu répondra en format markdown"
    f"\nUser Memories:\n{memories_str}"
)
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message}
    ]
    assistant_response =""
    total_assistant_content = ""
    # 2. Récupération des outils MCP dynamiques
    # On le fait à chaque appel pour être sûr d'avoir les outils à jour
    available_tools = await tools.get_all_tools()
    thinking_tool = [t for t in available_tools if t['function']['name'] == 'sequential_thinking']
    print(thinking_tool)

    # -----------------------------------------------------------------------
    try:
        while True:
            stream = await client.chat(
            model='qwen3:8b',
            messages=messages,
            tools=available_tools,
            stream=True,
            think = True

            )

            thinking = ''
            content = ''
            tool_calls = []

            done_thinking = False
            # accumulate the partial fields
            async for chunk in stream:
                if chunk.message.thinking:
                    thinking += chunk.message.thinking
                    print(chunk.message.thinking, end='', flush=True)
                    yield f"think {chunk.message.thinking}"
                if chunk.message.content:
                    if not done_thinking:
                        done_thinking = True
                        total_assistant_content += chunk.message.content
                        yield chunk.message.content
                        print('\n')
                    content += chunk.message.content
                    print(chunk.message.content, end='', flush=True)
                if chunk.message.tool_calls:
                    tool_calls.extend(chunk.message.tool_calls)
                    print(chunk.message.tool_calls)

  # append accumulated fields to the messages
            if thinking or content or tool_calls:
                messages.append({'role': 'assistant', 'thinking': thinking, 'content': content, 'tool_calls': tool_calls})

            if not tool_calls:
                break
            for call in tool_calls:
                yield f"\n*Jean-Heude utilise l'outil : {call.function.name}...*\n"
                
                # Exécution
                result = await tools.call_tool_execution(call.function.name, call.function.arguments)
                
                # On ajoute le résultat au contexte pour le tour suivant
                messages.append({
                    'role': 'tool',
                    'tool_name': call.function.name,
                    'content': str(result)
                })
        # 7. SAUVEGARDE EN MÉMOIRE
        if assistant_response.strip():
            conversation = [
                {"role": "user", "content": message},
                {"role": "assistant", "content": assistant_response}
            ]
            mem.add(conversation, user_id=user_id)

    except Exception as e:
        error_msg = f"Erreur Jean-Heude : {str(e)}"
        print(f"DEBUG ERROR: {error_msg}")
        yield error_msg
