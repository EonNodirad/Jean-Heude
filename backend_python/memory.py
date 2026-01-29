
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
        blacklist = ["embed", "classification", "rerank","vision","mini"]
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
    "CONSIGNES CRITIQUES :\n"
    "1. Tu as des capacités TECHNIQUES réelles via des fonctions (tools).\n"
    "2. Ne dis JAMAIS 'Je vais chercher' ou 'Je vais utiliser un outil'. FAIS-LE directement.\n"
    "3. Si l'utilisateur demande une info en temps réel (météo, news, prix), tu DOIS déclencher un outil de recherche.\n"
    "4. Tu as l'interdiction formelle d'inventer des faits ou des dates.\n"
    "5.Avant chaque action, utilise 'sequential_thinking' pour planifier ta réponse.\n"
    "6. Si tu ne trouves rien avec tes outils, réponds : 'Désolé, mes recherches n'ont rien donné.'\n"
    f"\nUser Memories:\n{memories_str}"
)
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message}
    ]
    
    assistant_response = ""
    max_itéraions = 5
    # 2. Récupération des outils MCP dynamiques
    # On le fait à chaque appel pour être sûr d'avoir les outils à jour
    available_tools = await tools.get_all_tools()
    thinking_tool = [t for t in available_tools if t['function']['name'] == 'sequential_thinking']
    print(thinking_tool)
    try:
        response = await client.chat(model= chosen_model, messages=messages, tools = thinking_tool)
        # 3. Premier appel : L'IA analyse si elle a besoin d'un outil
        for i in range(max_itéraions):
            response = await client.chat(
            model=chosen_model,
            messages=messages,
            tools=available_tools,
        )

        # 4. GESTION DES OUTILS (LOOP)
            if response.get('message', {}).get('tool_calls'):
            # On ajoute le message de l'assistant qui demande l'outil au contexte
                messages.append(response['message'])
            
                for tool in response['message']['tool_calls']:
                    tool_name = tool['function']['name']
                    tool_args = tool['function']['arguments']
                
                    yield f"Jean-Heude utilise l'outil : {tool_name}*...\n\n"
                
                # Exécution de l'outil (via MCP ou Natif)
                    result = await tools.call_tool_execution(tool_name, tool_args)
                
                # On ajoute la réponse de l'outil au contexte
                    messages.append({
                    "role": "tool",
                    "content": str(result), # Toujours s'assurer que c'est du texte
                    })


        
        # 6. RÉPONSE DIRECTE (Sans outil)
            else:
                stream = await client.chat(model=chosen_model, messages=messages, stream=True)
                async for chunk in stream:
                    content = chunk['message']['content']
                    assistant_response += content
                    yield content
                break

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
