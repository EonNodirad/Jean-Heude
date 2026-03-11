import asyncio
import uuid
import os
import tools
from database.sqlite_repo import SQLiteRepo
from database.qdrant_repo import QdrantRepo
import graph_memory

class MemoryManager:
    """
    Facade class managing access to all database repositories (SQLite, Qdrant, Neo4j).
    Provides a clean interface for the Agent logic to retrieve context and save history.
    """
    def __init__(self):
        self.sqlite = SQLiteRepo("memory/memoire.db")
        
        url_qdrant = os.environ.get("URL_QDRANT", "localhost")
        self.qdrant = QdrantRepo(host=url_qdrant, port=6333)
        
        # Uses the singleton graph database connection from graph_memory.py
        self.graph = graph_memory.graph_db

    async def create_session(self, user_id: str, resume: str) -> int:
        """Crée une nouvelle session de chat dans SQLite."""
        return await self.sqlite.create_session(resume, user_id)

    async def save_message(self, user_id: str, session_id: int, role: str, content: str, image_path: str = None):
        """Sauvegarde un message (user ou assistant) dans SQLite."""
        await self.sqlite.add_memory_chat(role, content, session_id, image_path)

    async def get_recent_history(self, session_id: int, limit: int = 20) -> list:
        """Récupère les derniers messages d'une session."""
        return await self.sqlite.get_recent_memory_chat(session_id, limit)

    async def get_hybrid_context(self, user_id: str, prompt: str, limit: int = 5) -> str:
        """
        Interroge simultanément Qdrant (Sémantique), SQLite (Mots-clés) et Neo4j (Graphe).
        Retourne un contexte formaté prêt à être injecté dans le prompt système.
        """
        # 1. Préparation des requêtes parallèles
        vector_task = tools._get_tool_embedding(prompt)
        keywords = prompt.split()
        
        qdrant_memories = []
        sqlite_memories = []
        graph_context = ""

        # 2. Exécution parallèle
        vector = await vector_task
        async def fetch_q() -> list:
            if not vector: return []
            try:
                return await self.qdrant.search_memories("jean_heude_memories", vector, user_id, limit)
            except Exception as e:
                print(f"⚠️ Erreur Qdrant dans get_hybrid_context: {e}")
                return []

        async def fetch_s() -> list:
            if not keywords: return []
            try:
                k_results = await self.sqlite.search_keyword_memory(keywords)
                return k_results
            except Exception as e:
                print(f"⚠️ Erreur SQLite dans get_hybrid_context: {e}")
                return []

        async def fetch_g() -> str:
            try:
                return await self.graph.search_graph(prompt, user_id)
            except Exception as e:
                print(f"⚠️ Erreur Neo4j dans get_hybrid_context: {e}")
                return ""

        # Gather results
        results = await asyncio.gather(fetch_q(), fetch_s(), fetch_g(), return_exceptions=True)
        qdrant_res = results[0] if not isinstance(results[0], Exception) else []
        sqlite_res = results[1] if not isinstance(results[1], Exception) else []
        graph_context = results[2] if not isinstance(results[2], Exception) else ""

        # 3. Consolidation et formatage (Mémoire Long Terme)
        memories_list = []
        for text in qdrant_res:
            if text not in memories_list:
                memories_list.append(text)
        for text in sqlite_res:
            if text not in memories_list:
                memories_list.append(text)

        memories_str = "\n".join([f"- {m}" for m in memories_list])
        
        # Format final
        hybrid_context = ""
        if graph_context:
            hybrid_context += f"--- CONTEXTE RELATIONNEL (GRAPHE) ---\n{graph_context}\n\n"
        
        hybrid_context += "--- SOUVENIRS CONCERNANT L'UTILISATEUR (MÉMOIRE LONG TERME) ---\n"
        hybrid_context += f"{memories_str if memories_str else 'Aucun souvenir spécifique.'}\n"
        
        return hybrid_context

    async def get_web_knowledge_context(self, prompt: str) -> str:
        """Recherche dans la collection de base commune web cache."""
        try:
            query_vector = await tools._get_tool_embedding(prompt)
            if not query_vector:
                return ""
                
            results = await self.qdrant.client.query_points(
                collection_name="jean_heude_knowledge",
                query=query_vector,
                limit=5,
                score_threshold=0.7
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
                
            web_context = "\n".join(extracted)
            if web_context:
                return f"--- SAVOIR RÉCENT (WEB CACHE) ---\n{web_context}\n\n"
            return ""
        except Exception as e:
            print(f"⚠️ Erreur rappel connaissance web: {e}")
            return ""

    async def process_new_facts(self, user_id: str, facts: str):
        """Sauvegarde les faits compressés dans Qdrant (Sémantique), SQLite (Index Long Terme) et Neo4j (Graphe)"""
        if not facts.strip():
            return
            
        print("💾 [MemoryManager] Sauvegarde des nouveaux faits dans les bases long terme...")
        
        # 1. Insertion Neo4j (Graphe ontologique)
        try:
            donnees_graphe = await graph_memory.extract_ontology(facts)
            await self.graph.insert_graph_data(donnees_graphe, user_id)
        except Exception as e:
            print(f"⚠️ Erreur extraction Neo4j lors de process_new_facts: {e}")

        # 2. Vectorisation et insertion (Qdrant + SQLite Index)
        try:
            vector = await tools._get_tool_embedding(facts)
            if vector:
                v_id = str(uuid.uuid4())
                await self.qdrant.upsert_memory(
                    collection_name="jean_heude_memories",
                    v_id=v_id,
                    vector=vector,
                    content=facts,
                    user_id=user_id
                )
                await self.sqlite.add_long_term_index(facts, v_id)
        except Exception as e:
            print(f"⚠️ Erreur Qdrant/SQLite lors de process_new_facts: {e}")

# Instance globale (Singleton) pour une utilisation facilitée (Facade partagée)
memory_manager = MemoryManager()
