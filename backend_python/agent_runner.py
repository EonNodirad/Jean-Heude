# agent_runner.py
import aiosqlite
import memory
import re
import os
import tools
import tiktoken
from ollama import AsyncClient
from functools import wraps

def session_guard(func):
    """Garantit que chaque agent dispose d'un espace de travail isolé."""
    @wraps(func)
    async def wrapper(self, text_content: str, session_id: int | None, on_token_callback):
        print(f"🛡️ [Session Guard] Isolation de la session {session_id or 'Nouvelle'}")
        return await func(self, text_content, session_id, on_token_callback)
    return wrapper


class AgentRunner:
    def __init__(self):
        self.encoder = tiktoken.get_encoding("cl100k_base")
        self.max_tokens = 5000  # Limite avant compaction du prompt
        
        # Client LLM dédié aux tâches administratives (résumé et extraction)
        self.admin_client = AsyncClient(host=os.getenv("URL_SERVER_OLLAMA"))
        self.admin_model = "llama3.1:8b" 
        
    def count_tokens(self, messages: list) -> int:
        """Compte les jetons d'un historique complet."""
        text = " ".join([str(m["content"]) for m in messages])
        return len(self.encoder.encode(text))

    async def _context_window_guard(self, history: list) -> list:
        """
        Génère un prompt compressé (Head + Résumé + Tail) À LA VOLÉE.
        Ne modifie AUCUNE base de données pour préserver l'UI.
        """
        print("🧹 [Context Guard] Fenêtre pleine. Compaction en mémoire...")
        
        if len(history) <= 4:
            return history
            
        head = history[:2]   # Les 2 premiers (souvent le début de conversation)
        tail = history[-2:]  # Les 2 derniers (le contexte immédiat)
        middle = history[2:-2] # Le corps à compresser
        
        middle_text = "\n".join([f"{m['role']}: {m['content']}" for m in middle])
        
        # 1. Extraction des faits (Pre-Compaction Memory Flush)
        print("💾 [Context Guard] Extraction des faits vers le long terme...")
        flush_prompt = (
            f"Analyse cet historique et liste uniquement les faits nouveaux et importants "
            f"concernant l'utilisateur. Sois très concis, sous forme de tirets. "
            f"S'il n'y a rien d'important, réponds 'AUCUN'.\n\nHistorique:\n{middle_text}"
        )
        res_facts = await self.admin_client.chat(model=self.admin_model, messages=[{"role": "user", "content": flush_prompt}])
        facts = res_facts.message.content.strip()
        
        if "aucun" not in facts.lower() and len(facts) > 5:
            # On sauvegarde les faits dans la mémoire longue (qui est souveraine)
            with open("memory/MEMORY.md", "a", encoding="utf-8") as f:
                f.write(f"\n{facts}\n")
            await memory.sync_memory_md()
            print("✅ [Context Guard] Faits persistés dans MEMORY.md et indexés.")

        # 2. Algorithme de compaction (pour le prompt LLM uniquement)
        print("📉 [Context Guard] Création du résumé pour le prompt...")
        compact_prompt = f"Résume cette partie de la conversation en 3 phrases maximum.\n\nHistorique:\n{middle_text}"
        res_compact = await self.admin_client.chat(model=self.admin_model, messages=[{"role": "user", "content": compact_prompt}])
        summary = res_compact.message.content.strip()
        
        compressed_history = head + [{"role": "system", "content": f"RÉSUMÉ DES ÉCHANGES PRÉCÉDENTS: {summary}"}] + tail
        
        print("✅ [Context Guard] Compaction mémoire terminée.")
        # On retourne la liste compressée pour l'envoyer au LLM
        return compressed_history
    async def process_multimodal_chat(self, prompt: str, image_b64: str | None,image_path: str|None, session_id: int, stream_callback):
        print(f"⚙️ AgentRunner: Traitement multimodal pour session {session_id}")
        
        # 1. On charge l'historique directement depuis SQLite
        memory_context = []
        if session_id:
            async with aiosqlite.connect("memory/memoire.db") as db:
                async with db.execute("SELECT role, content FROM memory_chat WHERE sessionID = ? ORDER BY timestamp ASC LIMIT 20", (session_id,)) as cursor:
                    lignes = await cursor.fetchall()
                    for ligne in lignes:
                        memory_context.append({"role": ligne[0], "content": ligne[1]})
        
        # 2. Le System Prompt spécifique à la vision
        system_prompt = {
            "role": "system",
            "content": (
                "Tu es Jean-Heude, un assistant personnel intelligent et capable d'analyser des images.\n"
            )
        }
        
        # 3. Message utilisateur avec l'image
        user_message = {"role": "user", "content": prompt}
        if image_b64:
            user_message["images"] = [image_b64]
            print("🖼️ Image B64 injectée avec succès pour Qwen3-VL.")

        full_messages = [system_prompt] + memory_context + [user_message]
        vision_model = "qwen3-vl:8b" 

        # 4. Récupération des outils pertinents
        relevant_tools = await tools.get_relevant_tools(prompt, limit=3)

        # 5. On prépare une variable pour stocker la réponse finale de l'assistant
        assistant_final_text = ""

        async for token in memory.execute_agent_loop(full_messages, vision_model, available_tools=relevant_tools, mute_audio=True):
            await stream_callback(token)
            
            # On attrape les mots au vol, on ignore la pensée (¶) et l'audio
            clean_chunk = re.sub(r'\|\|AUDIO_ID:.*?\|\|', '', token)
            if not clean_chunk.startswith("¶"): 
                assistant_final_text += clean_chunk
        
        # 6. Sauvegarde BDD (Utilisateur ET Assistant)
        if session_id:
            async with aiosqlite.connect("memory/memoire.db") as db:
                
                # Astuce magique : On ajoute la colonne 'image' dans la table si elle n'existe pas !
                try:
                    await db.execute("ALTER TABLE memory_chat ADD COLUMN image TEXT")
                except Exception:
                    pass # Si ça fait une erreur, c'est que la colonne existe déjà, on ignore.
                
                # NOUVEAU : On insère le prompt AVEC le chemin de l'image (image_path)
                await db.execute(
                    "INSERT INTO memory_chat (role, content, timestamp, sessionID, image) VALUES (?, ?, datetime('now'), ?, ?)",
                    ("user", prompt, session_id, image_path)
                )
                
                if assistant_final_text.strip():
                    # L'assistant n'a pas d'image, donc on met None à la fin
                    await db.execute(
                        "INSERT INTO memory_chat (role, content, timestamp, sessionID, image) VALUES (?, ?, datetime('now'), ?, ?)",
                        ("assistant", assistant_final_text.strip(), session_id, None)
                    )
                await db.commit()

    @session_guard
    async def process_chat(self, text_content: str, session_id: int | None, on_token_callback):
        async with aiosqlite.connect("memory/memoire.db") as db:
            # 1. Gestion Session
            if session_id is None:
                resume = text_content[:30] + "..."
                cursor = await db.execute(
                    "INSERT INTO historique_chat (timestamp, resume, userID) VALUES (datetime('now'), ?, ?)",
                    (resume, "noe_01")
                )
                await db.commit()
                session_id = cursor.lastrowid
                print(f"🆕 Nouvelle session créée : ID {session_id}")

            # 2. Sauvegarde INTACTE du message (pour Svelte)
            await db.execute(
                "INSERT INTO memory_chat (role, content, timestamp, sessionID) VALUES (?, ?, datetime('now'), ?)",
                ("user", text_content, session_id)
            )
            await db.commit()
            
            # 3. Récupération de l'historique pour le LLM
            cursor = await db.execute( 
                "SELECT role, content FROM memory_chat WHERE sessionID = ? ORDER BY timestamp DESC LIMIT 20",
                (session_id,)
            )
            lignes = await cursor.fetchall()
            contexte_message = [{"role" : m[0], "content": m[1] } for m in reversed(lignes)]

        # --- 4. DÉCLENCHEMENT DU CONTEXT GUARD (En mémoire uniquement) ---
        current_tokens = self.count_tokens(contexte_message)
        if current_tokens > self.max_tokens:
            # On écrase contexte_message avec la version compressée, MAIS la DB reste intacte !
            contexte_message = await self._context_window_guard(contexte_message)

        # 5. Sélection du modèle et Génération
        chosen_model = await memory.decide_model(text_content)
        print(f"🧠 Modèle choisi : {chosen_model}")

        assistant_final_text = ""
        
        async for chunk in memory.chat_with_memories(contexte_message, chosen_model):
            await on_token_callback(chunk)
            clean_chunk = re.sub(r'\|\|AUDIO_ID:.*?\|\|', '', chunk)
            if not clean_chunk.startswith("¶"): 
                assistant_final_text += clean_chunk
        
        # 6. Sauvegarde INTACTE de la réponse (pour Svelte)
        if assistant_final_text.strip():
            async with aiosqlite.connect("memory/memoire.db") as db_final:
                await db_final.execute(
                    "INSERT INTO memory_chat (role, content, timestamp, sessionID) VALUES (?, ?, datetime('now'), ?)",
                    ("assistant", assistant_final_text, session_id)
                )
                await db_final.commit()
                print("✅ Réponse assistant sauvegardée dans l'UI.")

        return {"session_id": session_id, "model": chosen_model}
