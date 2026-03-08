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

# Client Qdrant
client_qdrant = AsyncQdrantClient(host=url_qdrant, port=6333)

# 👤 AJOUT DU user_id
async def sync_memory_md(user_id: str):
    """Synchronise la mémoire spécifique de l'utilisateur."""
    # ✅ CHEMINS DYNAMIQUES
    user_dir = f"memory/users/{user_id}"
    file_path = f"{user_dir}/system/MEMORY.md"
    db_path = f"{user_dir}/memoire.db"
    
    if not os.path.exists(file_path):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"# Mémoire Long Terme de {user_id}\n\n")
            f.write("- Je viens de me réveiller. Ma mémoire est encore vierge.\n")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM long_term_index")
        
        for line in lines:
            content = line.strip("- \n")
            if len(content) < 5: 
                continue

            vector = await tools._get_tool_embedding(content)
            v_id = str(uuid.uuid4())
            
            # 🛡️ AJOUT DU PAYLOAD user_id
            await client_qdrant.upsert(
                collection_name="jean_heude_memories",
                points=[models.PointStruct(id=v_id, vector=vector, payload={"text": content, "user_id": user_id})]
            )

            await db.execute("INSERT INTO long_term_index (chunk_text, vector_id) VALUES (?, ?)", (content, v_id))
        await db.commit()


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


# ----------------- RECHERCHE HYBRIDE -----------------

async def chat_with_memories(history: list, chosen_model: str, user_id: str = "default_user") -> AsyncGenerator[str,Any]:
    
    async with memory_lock:
        last_user_message = next((m['content'] for m in reversed(history) if m['role'] == 'user'), "")
        print(f"🔍 Recherche mémoire hybride pour : {last_user_message}")
        
        memories_list = []
        
        # 1. Recherche par SENS (Qdrant)
        # 1. Recherche par SENS (Qdrant)
        try:
            vector = await tools._get_tool_embedding(last_user_message)
            v_results = await client_qdrant.query_points(
                collection_name="jean_heude_memories",
                query=vector,
                limit=5,
                query_filter=models.Filter(
                    must=[models.FieldCondition(key="user_id", match=models.MatchValue(value=user_id))]
                )
            )
            for hit in v_results.points:
                # Extraction propre (Type-Safe pour Pyright)
                payload = getattr(hit, "payload", None)
                text = None
                
                if isinstance(payload, dict):
                    text = payload.get("text")
                elif isinstance(hit, dict):
                    payload_dict = hit.get("payload")
                    if isinstance(payload_dict, dict):
                        text = payload_dict.get("text")
                        
                if isinstance(text, str) and text.strip():
                    memories_list.append(text.strip())
                    
        except Exception as e:
            print(f"⚠️ Erreur Qdrant : {e}")

        # 2. Recherche par MOTS-CLÉS (SQLite)
        keywords = last_user_message.split()
        if keywords:
            sql_query = "SELECT chunk_text FROM long_term_index WHERE " + " OR ".join(["chunk_text LIKE ?"] * len(keywords))
            params = [f"%{k}%" for k in keywords]
            # ✅ CHEMIN DYNAMIQUE
            async with aiosqlite.connect(f"memory/users/{user_id}/memoire.db") as db:
                async with db.execute(sql_query, params) as cursor:
                    k_results = await cursor.fetchall()
                    for row in k_results:
                        if row[0] not in memories_list:
                            memories_list.append(row[0])

        memories_str = "\n".join([f"- {m}" for m in memories_list])
        print("✅ Fin de la recherche mémoire")

    bloc_souvenirs = (
        "--- SOUVENIRS CONCERNANT L'UTILISATEUR (MÉMOIRE LONG TERME) ---\n"
        f"{memories_str if memories_str else 'Aucun souvenir spécifique.'}\n"
    )

    # 2. On fusionne avec le contexte venant de AgentRunner
    messages = []
    system_merged = False
    
    for msg in history:
        if msg["role"] == "system" and not system_merged:
            nouveau_contenu = msg["content"] + "\n\n" + bloc_souvenirs + "\nTu es Jean-Heude, un assistant personnel franc et objectif. Réponds de manière claire et naturelle."
            messages.append({"role": "system", "content": nouveau_contenu})
            system_merged = True
        else:
            messages.append(msg)
            
    if not system_merged:
        messages.insert(0, {"role": "system", "content": f"Tu es Jean-Heude.\n{bloc_souvenirs}"})

    assistant_final_text = ""
    
    available_tools = await tools.get_relevant_tools(last_user_message, limit=20)

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