import os
import asyncio
import re
import uuid
import time
import httpx
import aiosqlite
from typing import AsyncGenerator, Any
from dotenv import load_dotenv
import tools
from IA import Orchestrator
from ollama import AsyncClient
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from database.file_repo import FileRepo
from database.memory_manager import memory_manager

# --- Configurations Initiales ---
load_dotenv()

# ✅ CORRECTION 1 : os.environ.get avec fallback (Pyright est content, c'est toujours un str)
remote_host = os.environ.get("URL_SERVER_OLLAMA", "http://localhost:11434")
url_qdrant = os.environ.get("URL_QDRANT", "localhost")
TTS_SERVER_URL = os.environ.get("TTS_SERVER_URL", "http://localhost:5002/api/tts")

http_client = httpx.AsyncClient(timeout=20.0)
orchestrator = Orchestrator()
client = AsyncClient(host=remote_host)
model = "phi3:mini"

audio_store = {}
memory_lock = asyncio.Lock()

# 👤 AJOUT DU user_id
async def sync_memory_md(user_id: str):
    """Synchronise la mémoire spécifique de l'utilisateur."""
    is_new = FileRepo.init_memory_md(user_id)
    if is_new:
        return

    lines = FileRepo.read_memory_md(user_id)

    await memory_manager.sqlite.init_db()
    await memory_manager.sqlite.clear_long_term_index()
    
    for line in lines:
        content = line.strip("- \n")
        if len(content) < 5: 
            continue

        vector = await tools._get_tool_embedding(content)
        if not vector:
            continue

        v_id = str(uuid.uuid4())
        
        await memory_manager.qdrant.upsert_memory(
            collection_name="jean_heude_memories",
            v_id=v_id,
            vector=vector,
            content=content,
            user_id=user_id
        )

        await memory_manager.sqlite.add_long_term_index(content, v_id)


async def cleanup_audio_store():
    while True:
        try:
            await asyncio.sleep(60)
            now = time.time()
            to_delete = []
        
            for audio_id, entry in audio_store.items():
                if now - entry.get("created_at", 0) > 300 and entry.get("status") != "streaming":
                    to_delete.append(audio_id)
        
            for audio_id in to_delete:
                audio_store.pop(audio_id, None)
        except Exception as e:
            print(f"Erreur lors du cleanup : {e}")

def clean_text_for_tts(text):
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[\*\#\_\[\]\(\)\`]', '', text)
    text = text.replace('\n', ' ')
    return text.strip()


async def decide_model(message:str):
    relevant_tools = await tools.get_relevant_tools(message, limit=15)
    chosen_model = await orchestrator.choose_model(message, relevant_tools)
    print(f"--- 🎯 Décision : {chosen_model} ---")
    return chosen_model

def prepare_audio_slot():
    audio_id = str(uuid.uuid4())
    event = asyncio.Event()
    audio_store[audio_id] = {
        "data": None, 
        "event": event,
        "status": "pending",
        "created_at" : time.time()
    }
    return audio_id, event

async def pre_generate_audio(audio_id, text):
    try:
        entry = audio_store.get(audio_id)
        if not entry:
            print(f"⚠️ Audio {audio_id} déjà supprimé avant le début.")
            return

        entry.update({"chunks": [], "status": "streaming"})

        async with http_client.stream("POST", TTS_SERVER_URL, json={"text": text}) as response:
            if response.status_code == 200:
                first_chunk = True
                async for chunk in response.aiter_bytes():
                    if audio_id not in audio_store:
                        print(f"🛑 Stream interrompu : {audio_id} a été nettoyé.")
                        break
                        
                    audio_store[audio_id]["chunks"].append(chunk)
                    
                    if first_chunk:
                        audio_store[audio_id]["event"].set()
                        first_chunk = False
                
                if audio_id in audio_store:
                    audio_store[audio_id]["status"] = "done"
            else:
                if audio_id in audio_store:
                    audio_store[audio_id]["status"] = "error"
    except Exception as e:
        print(f"Erreur TTS : {e}")
        if audio_id in audio_store:
            audio_store[audio_id]["status"] = "error"
    finally:
        if audio_id in audio_store:
            audio_store[audio_id]["event"].set()


# ----------------- Helper Functions supprimées (Déléguées à MemoryManager) ----------

async def chat_with_memories(history: list, chosen_model: str, user_id: str = "default_user") -> AsyncGenerator[str,Any]:
    
    last_user_message = next((m['content'] for m in reversed(history) if m['role'] == 'user'), "")
    print(f"🔍 Recherche mémoire hybride et outils pour : {last_user_message}")

    # On lance SEULEMENT la sélection d'outils, le contexte est déjà dans l'history (préparé par agent_runner)
    tools_task = tools.get_relevant_tools(last_user_message, limit=20)
    available_tools = await tools_task

    print("✅ Fin de la recherche mémoire")

    # 2. Le contexte venant de AgentRunner est déjà prêt
    messages = history
    system_merged = False
    
    for msg in history:
        if msg["role"] == "system" and not system_merged:
            nouveau_contenu = msg["content"] + "\nTu es Jean-Heude, un assistant personnel franc et objectif. Réponds de manière claire et naturelle."
            msg["content"] = nouveau_contenu
            system_merged = True
            
    if not system_merged:
        messages.insert(0, {"role": "system", "content": f"Tu es Jean-Heude."})

    assistant_final_text = ""


    async for chunk in execute_agent_loop(messages, chosen_model, available_tools, user_id=user_id):
        if not chunk.startswith("¶") and not chunk.startswith("||AUDIO_ID:"):
            assistant_final_text += chunk
        yield chunk


async def execute_agent_loop(messages: list, chosen_model: str, available_tools: list, mute_audio: bool = False, user_id: str = "invite") -> AsyncGenerator[str, Any]:
    assistant_full_response = ""
    buffer_audio = ""
    is_in_hidden_thought = False
    
    caps = await orchestrator.get_model_details(chosen_model)
    # ✅ CORRECTION 2 : Filet de sécurité au cas où l'orchestrateur renvoie None
    if not caps:
        caps = {'can_think': False, 'can_use_tools': False}
        
    print(f" Jean-Heude utilise {chosen_model} | Think: {caps['can_think']} | Tools: {caps['can_use_tools']}")
    try:
        current_tools = available_tools if caps['can_use_tools'] else None
        while True:
            stream = await client.chat(
                model=chosen_model,
                messages=messages,
                tools=current_tools,
                stream=True,
                # On passe None au lieu de False si le modèle ne supporte pas explicitement "think" selon la version d'Ollama
                think=caps.get('can_think', False),
            )

            thinking = ''
            content = ''
            tool_calls = []
            done_thinking = False

            async for chunk in stream:
                # 1. Traitement de la pensée (Safe String)
                chunk_thinking = getattr(chunk.message, "thinking", None)
                if isinstance(chunk_thinking, str):
                    thinking += chunk_thinking
                    yield f"¶{chunk_thinking}"
                
                # 2. Traitement du contenu (Safe String)
                chunk_content = getattr(chunk.message, "content", None)
                if isinstance(chunk_content, str):
                    if not done_thinking:
                        done_thinking = True
                    
                    content += chunk_content
                    assistant_full_response += chunk_content
                    yield chunk_content

                    if "<think>" in chunk_content:
                        is_in_hidden_thought = True
                        yield "¶" 
                        continue 
                    
                    if "</think>" in chunk_content:
                        is_in_hidden_thought = False
                        continue

                    if is_in_hidden_thought:
                        yield f"¶{chunk_content}" 
                        continue

                    if not mute_audio and not is_in_hidden_thought:
                        clean_for_audio = chunk_content.replace("<think>", "").replace("</think>", "")
                        buffer_audio += clean_for_audio
                        
                        if any(p in chunk_content for p in [".", "!", "?", "\n", ";", ","]) or len(buffer_audio) > 40:
                            if len(buffer_audio.strip()) > 5:
                                audio_id, _ = prepare_audio_slot()
                                phrase = clean_text_for_tts(buffer_audio)
                                asyncio.create_task(pre_generate_audio(audio_id, phrase))
                                yield f"||AUDIO_ID:{audio_id}||"
                                buffer_audio = ""

                # 3. Traitement des appels d'outils (Safe Iterable)
                chunk_tools = getattr(chunk.message, "tool_calls", None)
                if chunk_tools is not None:
                    tool_calls.extend(chunk_tools)
                    await asyncio.sleep(0.01)
                    
            messages.append({'role': 'assistant', 'thinking': thinking, 'content': content, 'tool_calls': tool_calls})

            if not tool_calls:
                break

            for call in tool_calls:
                status_text = f"Utilisation de l'outil : {call.function.name}..."
                yield f"\n\n*{status_text}*\n\n"
                yield "\n"
                
                if not mute_audio and not is_in_hidden_thought:
                    status_audio_id, _ = prepare_audio_slot()
                    text_clean = clean_text_for_tts(status_text)
                    asyncio.create_task(pre_generate_audio(status_audio_id, text_clean))
                    yield f"||AUDIO_ID:{status_audio_id}||"

                result = await tools.call_tool_execution(call.function.name, call.function.arguments, user_id)

                messages.append({
                    'role': 'tool',
                    'name': call.function.name,
                    'content': str(result),
                    'tool_call_id': getattr(call, 'id', 'call_' + call.function.name)
                })

        if not mute_audio and buffer_audio.strip():
            final_audio_id, _ = prepare_audio_slot()
            phrase = clean_text_for_tts(buffer_audio.strip())
            asyncio.create_task(pre_generate_audio(final_audio_id, phrase))
            yield f"||AUDIO_ID:{final_audio_id}||"

    except Exception as e:
        yield f"Erreur dans la boucle agentique : {str(e)}"