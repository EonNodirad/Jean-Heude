from neo4j import AsyncGraphDatabase
import os

# Paramètres de connexion (qui correspondent au docker-compose)
URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
AUTH = ("neo4j", "jeanheude_password")

class GraphManager:
    def __init__(self):
        self.driver = AsyncGraphDatabase.driver(URI, auth=AUTH)

    async def close(self):
        await self.driver.close()

    async def check_connection(self):
        """Vérifie si le cerveau graphe est bien en ligne."""
        try:
            async with self.driver.session() as session:
                result = await session.run("RETURN 1 AS number")
                record = await result.single()
                if record and record["number"] == 1:
                    print("🕸️ [GraphRAG] Connexion à Neo4j établie avec succès !")
                    return True
        except Exception as e:
            print(f"❌ [GraphRAG] Erreur de connexion à Neo4j : {e}")
            return False

# Instance globale (Singleton) pour l'importer partout
graph_db = GraphManager()
