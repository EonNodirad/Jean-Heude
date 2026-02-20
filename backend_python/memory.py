import os
import asyncio
import re
import uuid
import time
import httpx
import aiosqlite
from typing import AsyncGenerator, Any
from dotenv import load_dotenv

from IA import Orchestrator
import tools
from ollama import AsyncClient
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

# --- Configurations Initiales ---
load_dotenv()
remote_host = os.getenv("URL_SERVER_OLLAMA")
url_qdrant = os.getenv("URL_QDRANT")
http_client = httpx.AsyncClient(timeout=20.0)
TTS_SERVER_URL = os.getenv("TTS_SERVER_URL")

orchestrator = Orchestrator()
client = AsyncClient(host=remote_host)
model = "phi3:mini"
_available_tools = None
audio_store = {}
memory_lock = asyncio.Lock()

# Client Qdrant
client_qdrant = AsyncQdrantClient(host=url_qdrant, port=6333)

# ----------------- NOUVEAU : GESTION HYBRIDE DE LA MÉMOIRE -----------------

async def _get_embedding(text: str):
    """Obtient le vecteur via le modèle Nomic d'Ollama"""
    response = await client.embeddings(model="nomic-embed-text", prompt=text)
    return response["embedding"]

async def sync_memory_md():
    """
    Synchronise MEMORY.md vers SQLite (Mots-clés) et Qdrant (Sens vectoriel).
    Si le fichier n'existe pas, on le crée proprement.
    """
    file_path = "memory/MEMORY.md"
    
    # 1. Si le fichier n'existe pas, on le crée avec une base vierge
    if not os.path.exists(file_path):
        print("📝 Fichier MEMORY.md introuvable. Création de la mémoire...")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("# Mémoire Long Terme de Jean-Heude\n\n")
            f.write("- Je viens de me réveiller. Ma mémoire est encore vierge.\n")
        
        # Le fichier vient d'être créé, inutile de l'indexer tout de suite
        return

    # 2. S'il existe, on le lit et on l'indexe (comme avant)
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    async with aiosqlite.connect("memory/memoire.db") as db:
        # Nettoyage de l'ancien index
        await db.execute("DELETE FROM long_term_index")
        
        for line in lines:
            content = line.strip("- \n")
            if len(content) < 5: 
                continue

            vector = await _get_embedding(content)
            v_id = str(uuid.uuid4())
            
            # Stockage Sémantique
            await client_qdrant.upsert(
                collection_name="jean_heude_memories",
                points=[models.PointStruct(id=v_id, vector=vector, payload={"text": content})]
            )

            # Stockage SQL
            await db.execute(
                "INSERT INTO long_term_index (chunk_text, vector_id) VALUES (?, ?)",
                (content, v_id)
            )
        await db.commit()
    print("✅ Index hybride (SQLite/Qdrant) synchronisé avec MEMORY.md")

# ----------------- FIN DE LA NOUVELLE GESTION -----------------


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

async def get_tools():
    global _available_tools
    if _available_tools is None:
        print("--- Chargement initial des outils... ---")
        _available_tools = await tools.get_all_tools()
    return _available_tools

async def decide_model(message:str):
    global _available_tools
    chosen_model = await orchestrator.choose_model(message, _available_tools)
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


# ----------------- MISE À JOUR : RECHERCHE HYBRIDE -----------------

async def chat_with_memories(history: list, chosen_model: str, user_id: str = "default_user") -> AsyncGenerator[str,Any]:
    
    async with memory_lock:
        last_user_message = next((m['content'] for m in reversed(history) if m['role'] == 'user'), "")
        print(f"🔍 Recherche mémoire hybride pour : {last_user_message}")
        
        memories_list = []
        
        # 1. Recherche par SENS (Qdrant)
        try:
            vector = await _get_embedding(last_user_message)
            v_results = await client_qdrant.query_points(
                collection_name="jean_heude_memories",
                query=vector,
                limit=3
            )
            for hit in v_results.points:
                if hasattr(hit, 'payload') and hit.payload:
                    # Cas 1 : C'est un bel objet
                    text = hit.payload.get("text")
                    if text: memories_list.append(text)
                elif isinstance(hit, dict) and "payload" in hit:
                    # Cas 2 : C'est un dictionnaire brut
                    text = hit["payload"].get("text")
                    if text: memories_list.append(text)
                elif isinstance(hit, tuple):
                    # Cas 3 : C'est un tuple (ton cas actuel). Le payload est le dictionnaire caché dedans !
                    for element in hit:
                        if isinstance(element, dict) and "text" in element:
                            memories_list.append(element["text"])
        except Exception as e:
            print(f"⚠️ Erreur Qdrant : {e}")

        # 2. Recherche par MOTS-CLÉS (SQLite)
        keywords = last_user_message.split()
        if keywords:
            sql_query = "SELECT chunk_text FROM long_term_index WHERE " + " OR ".join(["chunk_text LIKE ?"] * len(keywords))
            params = [f"%{k}%" for k in keywords]
            async with aiosqlite.connect("memory/memoire.db") as db:
                async with db.execute(sql_query, params) as cursor:
                    k_results = await cursor.fetchall()
                    for row in k_results:
                        if row[0] not in memories_list:
                            memories_list.append(row[0])

        memories_str = "\n".join([f"- {m}" for m in memories_list])
        print("✅ Fin de la recherche mémoire")

    system_prompt = (
    f"Tu es Jean-Heude, un assistant personnel franc et objectif.\n"
    "Tu répondras en format markdown.\n"
    "Donne une réponse claire, comme si c'était un dialogue oral.\n"
    f"\nSouvenirs concernant l'utilisateur :\n{memories_str}\n\n"
    "Utilise le contexte de la conversation ci-dessous pour répondre de manière cohérente."
    )
    
    messages = [{"role": "system", "content": system_prompt}] + history
    assistant_final_text = ""
    
    available_tools = await get_tools()

    async for chunk in execute_agent_loop(messages, chosen_model, available_tools):
        if not chunk.startswith("¶") and not chunk.startswith("||AUDIO_ID:"):
            assistant_final_text += chunk
        yield chunk

# ----------------- LE RESTE EST INTACT -----------------

async def execute_agent_loop(messages: list, chosen_model: str, available_tools: list) -> AsyncGenerator[str, Any]:
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
                if chunk.message.thinking:
                    thinking += chunk.message.thinking
                    yield f"¶{chunk.message.thinking}"
                
                if chunk.message.content:
                    if not done_thinking:
                        done_thinking = True
                    
                    text_chunk = chunk.message.content
                    content += text_chunk
                    assistant_full_response += text_chunk
                    yield text_chunk

                    if "<think>" in text_chunk:
                        is_in_hidden_thought = True
                        yield "¶" 
                        continue 
                    
                    if "</think>" in text_chunk:
                        is_in_hidden_thought = False
                        continue

                    if is_in_hidden_thought:
                        yield f"¶{text_chunk}" 
                        continue
                    
                    buffer_audio += text_chunk
                    if any(p in text_chunk for p in [".", "!", "?", "\n", ";", ","]) or len(buffer_audio) > 40:
                        if len(buffer_audio.strip()) > 5:
                            audio_id, _ = prepare_audio_slot()
                            phrase = clean_text_for_tts(buffer_audio)
                            asyncio.create_task(pre_generate_audio(audio_id, phrase))
                            yield f"||AUDIO_ID:{audio_id}||"
                            buffer_audio = ""

                if chunk.message.tool_calls:
                    tool_calls.extend(chunk.message.tool_calls)
                    await asyncio.sleep(0.01)

            messages.append({'role': 'assistant', 'thinking': thinking, 'content': content, 'tool_calls': tool_calls})

            if not tool_calls:
                break

            for call in tool_calls:
                status_text = f"Utilisation de l'outil : {call.function.name}..."
                yield f"\n*{status_text}*\n"
                yield "\n"
                
                status_audio_id, _ = prepare_audio_slot()
                text_clean = clean_text_for_tts(status_text)
                asyncio.create_task(pre_generate_audio(status_audio_id, text_clean))
                yield f"||AUDIO_ID:{status_audio_id}||"

                result = await tools.call_tool_execution(call.function.name, call.function.arguments)

                messages.append({
                    'role': 'tool',
                    'name': call.function.name,
                    'content': str(result),
                    'tool_call_id': getattr(call, 'id', 'call_' + call.function.name)
                })

        if buffer_audio.strip():
            final_audio_id, _ = prepare_audio_slot()
            phrase = clean_text_for_tts(buffer_audio.strip())
            asyncio.create_task(pre_generate_audio(final_audio_id, phrase))
            yield f"||AUDIO_ID:{final_audio_id}||"

    except Exception as e:
        yield f"Erreur dans la boucle agentique : {str(e)}"
