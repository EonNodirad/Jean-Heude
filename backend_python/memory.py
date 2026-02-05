
import os
import io
from IA import Orchestrator
from mem0 import Memory 
from typing import AsyncGenerator, Any
import tools
from ollama import AsyncClient
from dotenv import load_dotenv
import uuid
import asyncio
import re

import httpx

audio_store ={}



load_dotenv()
remote_host = os.getenv("URL_SERVER_OLLAMA")
url_qdrant = os.getenv("URL_QDRANT")
http_client = httpx.AsyncClient(timeout=20.0)
TTS_SERVER_URL = os.getenv("TTS_SERVER_URL")
orchestrator = Orchestrator()
client = AsyncClient(host=remote_host)

model = "phi3:mini"
    
_available_tools = None

def clean_text_for_tts(text):
    # 1. Supprime les URL (ça tue le temps de calcul)
    text = re.sub(r'https?://\S+', '', text)
    # 2. Supprime les symboles Markdown (*, #, _, [ ], ( ))
    text = re.sub(r'[\*\#\_\[\]\(\)\`]', '', text)
    # 3. Supprime les sauts de ligne excessifs
    text = text.replace('\n', ' ')
    return text.strip()

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

def get_memory():
    """Initialise la mémoire seulement au premier appel"""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = Memory.from_config(config)
    return _memory_instance

async def decide_model(message:str):
    global _available_tools
    
    # 2. On demande à l'orchestrateur de choisir en lui donnant cette liste
    # Note: Ton orchestrateur interne utilise un prompt similaire à celui ci-dessus
    chosen_model = await orchestrator.choose_model(message, _available_tools)
    
    print(f"--- 🎯 Décision : {chosen_model} ---")
    return chosen_model

async def pre_generate_audio(audio_id, text):
    try:
        response = await http_client.post(TTS_SERVER_URL, json={"text": text})
            
        if response.status_code == 200:
                # On stocke le binaire reçu dans ton audio_store habituel
            audio_store[audio_id] = io.BytesIO(response.content)
            print(f"✅ Audio {audio_id} généré par le service TTS et mis en cache")
        else:
            print(f"❌ Erreur serveur TTS distant : {response.status_code}")
                
    except Exception as e:
        print(f"❌ Erreur de liaison avec le service TTS: {e}")
        
async def chat_with_memories(history: list, chosen_model: str, user_id: str = "default_user") -> AsyncGenerator[str,Any]:
    # 1. Initialisation et récupération de la mémoire
    print("début mémoire")
    last_user_message = next((m['content'] for m in reversed(history) if m['role'] == 'user'), "")
    print(f" Recherche mémoires long terme pour : {last_user_message}")
    mem = get_memory()
    relevant_memories = mem.search(query=last_user_message, user_id=user_id, limit=3)
    
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
    "donne une réponse claire. "
    "Comme si c'était dialogue orals."
    f"\nUser Memories:\n{memories_str}"
    "Utilise le contexte de la conversation ci-dessous pour répondre de manière cohérente."
)
    
    messages = [{"role": "system", "content": system_prompt}]+ history
    assistant_final_text = ""
    # 2. Récupération des outils MCP dynamiques
    # On le fait à chaque appel pour être sûr d'avoir les outils à jour
    available_tools = await get_tools()
    print("tools ok")
    # -----------------------------------------------------------------------
    async for chunk in execute_agent_loop(messages, chosen_model, available_tools):
        # On accumule le texte pur pour la mémoire (en ignorant les tags spéciaux)
        if not chunk.startswith("¶") and not chunk.startswith("||AUDIO_ID:"):
            assistant_final_text += chunk
        
        yield chunk
    if assistant_final_text.strip():
        conversation = [
            {"role": "user", "content": last_user_message},
            {"role": "assistant", "content": assistant_final_text}
        ]
        mem.add(conversation, user_id=user_id)

async def execute_agent_loop(messages: list, chosen_model: str, available_tools: list) -> AsyncGenerator[str, Any]:
    """
    Gère la boucle de réflexion et d'exécution des outils (Agentic Loop).
    Yield des fragments de texte, des blocs de pensée et des IDs audio.
    """
    assistant_full_response = ""
    buffer_audio = ""
    is_in_hidden_thought = False
    caps = await orchestrator.get_model_details(chosen_model)
    
    print(f" Jean-Heude utilise {chosen_model} | Think: {caps['can_think']} | Tools: {caps['can_use_tools']}")
    try:
        current_tools = available_tools if caps['can_use_tools'] else None
        while True:
            stream = await client.chat(
                model=chosen_model,
                messages=messages,
                tools=current_tools,
                stream=True,
                think=caps['can_think'],
            )

            thinking = ''
            content = ''
            tool_calls = []
            done_thinking = False

            async for chunk in stream:
                # 1. Gestion du "Thinking"
                if chunk.message.thinking:
                    thinking += chunk.message.thinking
                    yield f"¶{chunk.message.thinking}"
                
                # 2. Gestion du Contenu (Réponse)
                if chunk.message.content:
                    if not done_thinking:
                        done_thinking = True
                    
                    text_chunk = chunk.message.content
                    content += text_chunk
                    assistant_full_response += text_chunk
                    yield text_chunk

                    if "<think>" in text_chunk:
                        is_in_hidden_thought = True
                        # On peut quand même envoyer la pensée au front avec le symbole ¶
                        yield "¶" 
                        continue 
                    
                    if "</think>" in text_chunk:
                        is_in_hidden_thought = False
                        continue

                    if is_in_hidden_thought:
                        yield f"¶{text_chunk}" # On l'envoie au front mais avec le tag pensée
                        continue
                    # --- Logique TTS intégrée ---
                    buffer_audio += text_chunk
                    if any(p in text_chunk for p in [".", "!", "?", "\n", ";", ","]) or len(buffer_audio) > 40:
                        if len(buffer_audio.strip()) > 5:
                            audio_id = str(uuid.uuid4())
                            phrase = clean_text_for_tts(buffer_audio)
                            asyncio.create_task(pre_generate_audio(audio_id, phrase))
                            yield f"||AUDIO_ID:{audio_id}||"
                            buffer_audio = ""

                # 3. Accumulation des appels d'outils
                if chunk.message.tool_calls:
                    tool_calls.extend(chunk.message.tool_calls)
                    await asyncio.sleep(0.01)

            # Mise à jour de l'historique pour l'IA
            messages.append({'role': 'assistant', 'thinking': thinking, 'content': content, 'tool_calls': tool_calls})

            # Si pas d'outils à appeler, on a fini !
            if not tool_calls:
                break

            # 4. Exécution des outils
            for call in tool_calls:
                status_text = f"Utilisation de l'outil : {call.function.name}..."
                yield f"\n*{status_text}*\n"
                yield "\n"
                
                # TTS pour le statut de l'outil
                status_audio_id = str(uuid.uuid4())
                text_clean = clean_text_for_tts(status_text)
                asyncio.create_task(pre_generate_audio(status_audio_id, text_clean))
                yield f"||AUDIO_ID:{status_audio_id}||"

                # Appel réel de l'outil via ton module tools
                result = await tools.call_tool_execution(call.function.name, call.function.arguments)

                messages.append({
                    'role': 'tool',
                    'name': call.function.name,
                    'content': str(result),
                    'tool_call_id': getattr(call, 'id', 'call_' + call.function.name)
                })

        # Gestion du reliquat audio à la fin
        if buffer_audio.strip():
            final_audio_id = str(uuid.uuid4())
            asyncio.create_task(pre_generate_audio(final_audio_id, buffer_audio.strip()))
            yield f"||AUDIO_ID:{final_audio_id}||"

    except Exception as e:
        yield f"Erreur dans la boucle agentique : {str(e)}"
