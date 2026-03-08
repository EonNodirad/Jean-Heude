# agent_runner.py
import aiosqlite
import memory_IA as memory
import re
import os
import tools
import datetime
import tiktoken
from ollama import AsyncClient
from functools import wraps
import graph_memory
from qdrant_client.http import models
from typing import Any

def session_guard(func):
    """Garantit que chaque agent dispose d'un espace de travail isolé."""
    @wraps(func)
    async def wrapper(self, text_content: str, session_id: int | None, on_token_callback, **kwargs):
        print(f"🛡️ [Session Guard] Isolation de la session {session_id or 'Nouvelle'}")
        return await func(self, text_content, session_id, on_token_callback, **kwargs)
    return wrapper

def get_user_dir(user_id: str) -> str:
    """Crée et retourne le chemin d'accès au dossier unique de l'utilisateur."""
    # On crée une arborescence propre : memory/users/noe_01/system/
    base_path = f"memory/users/{user_id}"
    os.makedirs(f"{base_path}/system", exist_ok=True)
    return base_path
class AgentRunner:
    def __init__(self):
        self.encoder = tiktoken.get_encoding("cl100k_base")
        self.max_tokens = 5000  # Limite avant compaction du prompt
        
        # Client LLM dédié aux tâches administratives (résumé et extraction)
        self.admin_client = AsyncClient(host=os.getenv("URL_SERVER_OLLAMA"))
        self.admin_model = "llama3.1:8b" 
        
    def _load_os_context(self, user_id: str) -> str:
        contexte = ""
        user_dir = get_user_dir(user_id)
        
        # Le fichier AGENTS.md propre à l'utilisateur
        path_agents = f"{user_dir}/system/AGENTS.md"
        if os.path.exists(path_agents):
            with open(path_agents, "r", encoding="utf-8") as f:
                contexte += f.read() + "\n\n"
                
        # Le fichier USER.md propre à l'utilisateur
        path_user = f"{user_dir}/system/USER.md"
        if os.path.exists(path_user):
            with open(path_user, "r", encoding="utf-8") as f:
                contexte += f"--- PROFIL DE L'UTILISATEUR ACTUEL ({user_id}) ---\n"
                contexte += f.read() + "\n\n"
        
        if not contexte.strip():
            contexte = "Tu es J.E.A.N-H.E.U.D.E, un assistant local souverain."
            
        return contexte
        return contexte
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
            user_dir = get_user_dir(user_id)
            with open(f"{user_dir}/system/MEMORY.md", "a", encoding="utf-8") as f:
                f.write(f"\n{facts}\n")
            
            # ⚠️ ATTENTION : sync_memory_md doit aussi être adapté (on le fera après dans memory.py)
            await memory.sync_memory_md(user_id)
            
            # 2. NOUVEAU : Sauvegarde Graphe !
            donnees_graphe = await graph_memory.extract_ontology(facts)
            # ⚠️ ATTENTION : insert_graph_data doit aussi être adapté pour isoler le graphe par utilisateur (on y reviendra)
            await graph_memory.graph_db.insert_graph_data(donnees_graphe,user_id)
            
            print("✅ [Context Guard] Faits persistés dans MEMORY.md et indexés dans le Graphe.")

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
        user_db_path = f"{get_user_dir(user_id)}/memoire.db"
        # 1. On charge l'historique directement depuis SQLite
        memory_context = []
        if session_id:
            async with aiosqlite.connect(user_db_path) as db:
                async with db.execute("SELECT role, content FROM memory_chat WHERE sessionID = ? ORDER BY timestamp ASC LIMIT 20", (session_id,)) as cursor:
                    lignes = await cursor.fetchall()
                    for ligne in lignes:
                        memory_context.append({"role": ligne[0], "content": ligne[1]})
        
        # 2. Le System Prompt spécifique à la vision
        os_context = self._load_os_context(user_id)
        graph_context = await graph_memory.graph_db.search_graph(prompt, user_id)
        
        system_prompt = {
            "role": "system",
            "content": (
                f"{os_context}\n\n"
                f"{graph_context}\n\n"
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

    async def _recall_web_knowledge(self, query: str) -> str:
        """Fouille dans la collection de savoir accumulé sur le web (Base Commune)."""
        try:
            query_vector = await tools._get_tool_embedding(query)
            
            results = await tools.qdrant.query_points(
                collection_name="jean_heude_knowledge",
                query=query_vector,
                limit=5,
                score_threshold=0.7
                # ❌ ON A RETIRÉ LE FILTRE : Il fouille dans les recherches de tout le monde !
            )
            
            if not results.points:
                return ""

            extracted = []
            for hit in results.points:

                payload = getattr(hit, "payload", None)
                
                if isinstance(payload, dict):
                    content = payload.get("contenu", "")
                    date = payload.get("date", "Date inconnue")
                    extracted.append(f"[Souvenir du {date}]: {content}")
                
            return "\n".join(extracted)
        except Exception as e:
            print(f"⚠️ Erreur rappel connaissance web: {e}")
            return ""
        
    @session_guard
    async def process_chat(self, text_content: str, session_id: int | None, user_id: str, on_token_callback, is_hidden: bool = False):
        user_db_path = f"{get_user_dir(user_id)}/memoire.db"
        async with aiosqlite.connect(user_db_path) as db:
            # 1. Gestion Session
            if session_id is None:
                resume = text_content[:30] + "..."
                cursor = await db.execute(
                    # 👤 NOUVEAU : On utilise la vraie variable user_id au lieu de "noe_01"
                    "INSERT INTO historique_chat (timestamp, resume, userID) VALUES (datetime('now'), ?, ?)",
                    (resume, user_id)
                )
                await db.commit()
                session_id = cursor.lastrowid
                print(f"🆕 Nouvelle session créée : ID {session_id} pour {user_id}")

            # ... (Sauvegarde INTACTE du message) ...
            
            # 3. Préparation du contexte
            # 👤 NOUVEAU : On passe le user_id pour charger le bon fichier
            os_context = self._load_os_context(user_id)
            graph_context = await graph_memory.graph_db.search_graph(text_content,user_id)
            
            # --- NOUVEAU : Récupération du savoir Web (Auto-Cache Qdrant) ---
            web_context = await self._recall_web_knowledge(text_content)
            
            # --- NOUVEAU : Date dynamique pour éviter le bug "2023" ---
            date_actuelle = datetime.datetime.now().strftime("%A %d %B %Y à %H:%M:%S")
            
            # Construction du super-prompt système
            system_content = (
                f"{os_context}\n\n"
                f"--- CONTEXTE RELATIONNEL (GRAPHE) ---\n{graph_context}\n\n"
            )
            
            if web_context:
                system_content += f"--- SAVOIR RÉCENT (WEB CACHE) ---\n{web_context}\n\n"
            
            system_content += (
                f"=== HORLOGE SYSTÈME ACTIVE ===\n"
                f"Date et Heure actuelles : {date_actuelle}\n"
                f"RÈGLE ABSOLUE : Tu AS accès à l'heure via ce prompt."
            )

            # Récupération de l'historique de conversation (les 20 derniers messages)
            cursor = await db.execute( 
                "SELECT role, content FROM memory_chat WHERE sessionID = ? ORDER BY timestamp DESC LIMIT 20",
                (session_id,)
            )
            lignes = await cursor.fetchall()
            
            # Assemblage final des messages
            contexte_message = [{"role": "system", "content": system_content}]
            
            contexte_message.extend([{"role": m[0], "content": m[1]} for m in reversed(list(lignes))])
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
            async with aiosqlite.connect(user_db_path) as db_final:
                await db_final.execute(
                    "INSERT INTO memory_chat (role, content, timestamp, sessionID) VALUES (?, ?, datetime('now'), ?)",
                    ("assistant", assistant_final_text.strip(), session_id)
                )
                await db_final.commit()
                print("✅ Réponse assistant sauvegardée.")

        return {"session_id": session_id, "model": chosen_model}
    

