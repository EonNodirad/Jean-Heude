from neo4j import AsyncGraphDatabase
import os
import json
from ollama import AsyncClient
import asyncio
from dotenv import load_dotenv

load_dotenv()
# Paramètres de connexion (qui correspondent au docker-compose)
URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USER")
PASSWORD = os.getenv("NEO4J_PASSWORD")
AUTH = (USER, PASSWORD)

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
    
    async def insert_graph_data(self, data: dict):
        """Injecte le JSON extrait par le LLM directement dans Neo4j."""
        if not data.get("nodes") and not data.get("edges"):
            return
            
        async with self.driver.session() as session:
            # 1. Création des Nœuds (Entités)
            for node in data.get("nodes", []):
                query = """
                MERGE (n:Entite {id: $id})
                SET n.type = $type
                """
                # On met tout en majuscules pour éviter les doublons (ex: "Python" vs "PYTHON")
                await session.run(query, id=str(node["id"]).upper(), type=str(node["type"]).upper())
            
            # 2. Création des Liens (Relations)
            for edge in data.get("edges", []):
                query = """
                MATCH (a:Entite {id: $source})
                MATCH (b:Entite {id: $target})
                MERGE (a)-[r:RELATION {type: $rel_type}]->(b)
                """
                await session.run(
                    query, 
                    source=str(edge["source"]).upper(), 
                    target=str(edge["target"]).upper(), 
                    rel_type=str(edge["relation"]).upper()
                )
    async def search_graph(self, query: str) -> str:
        """Cherche des entités dans le graphe et renvoie leur contexte."""
        # On extrait les mots de plus de 3 lettres de la question pour chercher dans le graphe
        mots_cles = [mot.upper() for mot in query.split() if len(mot) > 3]
        if not mots_cles:
            return ""

        contexte_trouve = ""
        async with self.driver.session() as session:
            for mot in mots_cles:
                # Requête Cypher : Trouve le nœud, et ramène ses voisins directs
                query_cypher = """
                MATCH (n:Entite)-[r:RELATION]->(m:Entite)
                WHERE n.id CONTAINS $mot OR m.id CONTAINS $mot
                RETURN n.id AS source, r.type AS relation, m.id AS target
                LIMIT 5
                """
                result = await session.run(query_cypher, mot=mot)
                records = await result.data()
                
                for record in records:
                    contexte_trouve += f"- {record['source']} [{record['relation']}] {record['target']}\n"
        
        if contexte_trouve:
            return f"CONTEXTE GRAPHE (Ne le mentionne que si c'est utile) :\n{contexte_trouve}"
        return ""

ollama_client = AsyncClient(host=os.getenv("URL_SERVER_OLLAMA"))

async def extract_ontology(text: str) -> dict:
    """Demande au LLM d'extraire le graphe de connaissances du texte."""
    prompt = f"""Analyse ce texte et extrais les entités et leurs relations.
Renvoie UNIQUEMENT un objet JSON avec cette structure exacte :
{{
  "nodes": [{{"id": "nom_entite", "type": "Personne|Projet|Techno|Concept"}}],
  "edges": [{{"source": "nom_entite_1", "target": "nom_entite_2", "relation": "TRAVAILLE_SUR|UTILISE|EST_LIE_A"}}]
}}
Texte: {text}"""

    print("🧠 [GraphRAG] Extraction de l'ontologie en cours...")
    response = await ollama_client.chat(
        model="llama3.1:8b", # Utilise ton modèle le plus rapide/intelligent ici
        messages=[{"role": "user", "content": prompt}],
        format="json" # MAGIQUE : Force la sortie en JSON valide
    )
    
    try:
        return json.loads(response.message.content)
    except Exception as e:
        print(f"❌ [GraphRAG] Erreur de parsing JSON : {e}")
        return {"nodes": [], "edges": []}
# Instance globale (Singleton) pour l'importer partout
graph_db = GraphManager()


async def test_graph():
    await graph_db.check_connection()
    
    texte_test = "Noé est un développeur Junior qui travaille sur le projet Jean-Heude. Jean-Heude utilise Python et SvelteKit."
    
    # 1. L'IA réfléchit
    donnees_extraites = await extract_ontology(texte_test)
    print("JSON Extrait :", json.dumps(donnees_extraites, indent=2))
    
    # 2. On injecte dans la base
    await graph_db.insert_graph_data(donnees_extraites)
    await graph_db.close()

if __name__ == "__main__":
    asyncio.run(test_graph())
