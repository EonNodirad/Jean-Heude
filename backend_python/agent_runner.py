import memory_IA as memory
import re
import os
import tools
import datetime
import tiktoken
import asyncio
from ollama import AsyncClient
from functools import wraps
from database.file_repo import FileRepo
from database.memory_manager import memory_manager

def session_guard(func):
    """Garantit que chaque agent dispose d'un espace de travail isolé."""
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        session_id = args[1] if len(args) > 1 else kwargs.get('session_id')
        print(f"🛡️ [Session Guard] Isolation de la session {session_id or 'Nouvelle'}")
        return await func(self, *args, **kwargs)
    return wrapper
class AgentRunner:
    def __init__(self):
        self.encoder = tiktoken.get_encoding("cl100k_base")
        self.max_tokens = 5000  # Limite avant compaction du prompt
        
        # Client LLM dédié aux tâches administratives (résumé et extraction)
        self.admin_client = AsyncClient(host=os.getenv("URL_SERVER_OLLAMA"))
        self.admin_model = "llama3.1:8b" 
        
    def _load_os_context(self, user_id: str) -> str:
        return FileRepo.load_os_context(user_id)
    def count_tokens(self, messages: list) -> int:
        """Compte les jetons d'un historique complet."""
        text = " ".join([str(m["content"]) for m in messages])
        return len(self.encoder.encode(text))

    async def _context_window_guard(self, history: list,user_id: str) -> list:
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
        
        # ✅ EXTRACTION SÉCURISÉE (Safe String)
        facts_content = getattr(res_facts.message, "content", "")
        facts = facts_content.strip() if isinstance(facts_content, str) else ""
        
        if "aucun" not in facts.lower() and len(facts) > 5:
            # ✅ CORRECTION : Écriture dans le BON dossier utilisateur
            FileRepo.append_fact_to_memory(user_id, facts)
            
            # ⚠️ ATTENTION : sync_memory_md doit aussi être adapté (on le fera après dans memory.py)
            await memory.sync_memory_md(user_id)
            
            # 2. NOUVEAU : Sauvegarde Globalisée via MemoryManager !
            await memory_manager.process_new_facts(user_id, facts)

        # 2. Algorithme de compaction (pour le prompt LLM uniquement)
        print("📉 [Context Guard] Création du résumé pour le prompt...")
        compact_prompt = f"Résume cette partie de la conversation en 3 phrases maximum.\n\nHistorique:\n{middle_text}"
        res_compact = await self.admin_client.chat(model=self.admin_model, messages=[{"role": "user", "content": compact_prompt}])
        
        # ✅ EXTRACTION SÉCURISÉE (Safe String)
        summary_content = getattr(res_compact.message, "content", "")
        summary = summary_content.strip() if isinstance(summary_content, str) else ""
        
        compressed_history = head + [{"role": "system", "content": f"RÉSUMÉ DES ÉCHANGES PRÉCÉDENTS: {summary}"}] + tail
        
        print("✅ [Context Guard] Compaction mémoire terminée.")
        # On retourne la liste compressée pour l'envoyer au LLM
        return compressed_history

    async def process_multimodal_chat(self, prompt: str, image_b64: str | None, image_path: str|None, session_id: int | None, user_id: str, stream_callback):
        print(f"⚙️ AgentRunner: Traitement multimodal pour session {session_id}")
        # 1. On charge l'historique directement depuis MemoryManager
        memory_context = []
        if session_id:
            memory_context = await memory_manager.get_recent_history(session_id, 20)
        
        # 2. Le System Prompt spécifique à la vision
        os_context = self._load_os_context(user_id)
        hybrid_context = await memory_manager.get_hybrid_context(user_id, prompt)
        
        system_prompt = {
            "role": "system",
            "content": (
                f"{os_context}\n\n"
                f"{hybrid_context}\n\n"
                "--- INSTRUCTION SPÉCIALE MULTIMODALE ---\n"
                "Tu as des yeux. Analyse l'image fournie avec une précision d'expert technique."
            )
        }
        
        # 3. Message utilisateur avec l'image
        user_message: dict[str, Any] = {"role": "user", "content": prompt}
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
            await memory_manager.save_message(user_id, session_id, "user", prompt, image_path)
            
            if assistant_final_text.strip():
                await memory_manager.save_message(user_id, session_id, "assistant", assistant_final_text.strip())

    # _recall_web_knowledge a été déplacé dans memory_manager.py
        
    @session_guard
    async def process_chat(self, text_content: str, session_id: int | None, user_id: str, on_token_callback, is_hidden: bool = False):
        # 1. Gestion Session
        if session_id is None:
            resume = text_content[:30] + "..."
            session_id = await memory_manager.create_session(user_id, resume)
            print(f"🆕 Nouvelle session créée : ID {session_id} pour {user_id}")

        # 2. Sauvegarde du message utilisateur
        await memory_manager.save_message(user_id, session_id, "user", text_content)
        
        # 3. Préparation du contexte (Optimisation RAM/Parallel)
        os_context = self._load_os_context(user_id)
        
        # Lancement parallèle des recherches de contexte
        web_context_task = memory_manager.get_web_knowledge_context(text_content)
        hybrid_context_task = memory_manager.get_hybrid_context(user_id, text_content)
        
        web_context, hybrid_context = await asyncio.gather(web_context_task, hybrid_context_task)
        
        date_actuelle = datetime.datetime.now().strftime("%A %d %B %Y à %H:%M:%S")
        
        # Construction du super-prompt système
        system_content = (
            f"{os_context}\n\n"
        )
        
        if hybrid_context:
            system_content += f"{hybrid_context}\n\n"
            
        if web_context:
            system_content += f"{web_context}\n\n"
        
        system_content += (
            f"=== HORLOGE SYSTÈME ACTIVE ===\n"
            f"Date et Heure actuelles : {date_actuelle}\n"
            f"RÈGLE ABSOLUE : Tu AS accès à l'heure via ce prompt."
        )

        # Récupération de l'historique de conversation (les 20 derniers messages)
        messages_db = await memory_manager.get_recent_history(session_id, 20)
        
        # Assemblage final des messages
        contexte_message = [{"role": "system", "content": system_content}]
        contexte_message.extend(messages_db)
        # --- 4. DÉCLENCHEMENT DU CONTEXT GUARD (Compaction si nécessaire) ---
        current_tokens = self.count_tokens(contexte_message)
        if current_tokens > self.max_tokens:
            contexte_message = await self._context_window_guard(contexte_message, user_id)

        # 5. Sélection du modèle et Génération
        chosen_model = await memory.decide_model(text_content)
        print(f"🧠 Modèle choisi : {chosen_model}")



        assistant_final_text = ""
        
        # Lancement de la boucle agentique
        async for chunk in memory.chat_with_memories(contexte_message, chosen_model):
            await on_token_callback(chunk)
            clean_chunk = re.sub(r'\|\|AUDIO_ID:.*?\|\|', '', chunk)
            if not clean_chunk.startswith("¶"): 
                assistant_final_text += clean_chunk
        
        # 6. Sauvegarde de la réponse dans la DB (pour l'UI)
        if assistant_final_text.strip():
            await memory_manager.save_message(user_id, session_id, "assistant", assistant_final_text.strip())
            print("✅ Réponse assistant sauvegardée.")

        return {"session_id": session_id, "model": chosen_model}
    

