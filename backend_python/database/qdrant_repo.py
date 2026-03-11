from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

class QdrantRepo:
    def __init__(self, host: str, port: int = 6333):
        self.client = AsyncQdrantClient(host=host, port=port)

    async def init_collection(self, collection_name: str, size: int = 768):
        try:
            await self.client.get_collection(collection_name)
        except Exception:
            print(f"📦 Création de la collection Qdrant '{collection_name}'...")
            await self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(size=size, distance=models.Distance.COSINE),
            )

    async def upsert_memory(self, collection_name: str, v_id: str, vector: list[float], content: str, user_id: str):
        await self.client.upsert(
            collection_name=collection_name,
            points=[models.PointStruct(id=v_id, vector=vector, payload={"text": content, "user_id": user_id})]
        )

    async def search_memories(self, collection_name: str, vector: list[float], user_id: str, limit: int = 5) -> list[str]:
        memories_list = []
        try:
            v_results = await self.client.query_points(
                collection_name=collection_name,
                query=vector,
                limit=limit,
                query_filter=models.Filter(
                    must=[models.FieldCondition(key="user_id", match=models.MatchValue(value=user_id))]
                )
            )
            for hit in v_results.points:
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
            
        return memories_list

    async def search_knowledge(self, collection_name: str, vector: list[float], limit: int = 5, score_threshold: float = 0.7) -> list[dict]:
        results = []
        try:
            v_results = await self.client.query_points(
                collection_name=collection_name,
                query=vector,
                limit=limit,
                score_threshold=score_threshold
            )
            for hit in v_results.points:
                payload = getattr(hit, "payload", None)
                if isinstance(payload, dict):
                    results.append(payload)
        except Exception as e:
            print(f"⚠️ Erreur rappel connaissance web: {e}")
        return results
