import os
import json
import importlib.util
import uuid
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from ollama import AsyncClient

SKILLS_DIR = "skills"

# Connexions locales pour le JIT
qdrant = AsyncQdrantClient(host=os.getenv("URL_QDRANT", "localhost"), port=6333)
ollama_client = AsyncClient(host=os.getenv("URL_SERVER_OLLAMA", "http://localhost:11434"))

async def _get_tool_embedding(text: str):
    """Génère un vecteur pour la description de l'outil."""
    response = await ollama_client.embeddings(model="nomic-embed-text", prompt=text)
    return response["embedding"]

async def sync_skills_to_qdrant():
    """Indexe tous les skills présents dans le dossier /skills au démarrage."""
    if not os.path.exists(SKILLS_DIR):
        os.makedirs(SKILLS_DIR)
        print("📁 Dossier /skills créé.")
        return

    # 1. Préparation de la collection Qdrant pour les Skills
    try:
        await qdrant.get_collection("jean_heude_skills")
    except Exception:
        print("📦 Création de la collection Qdrant 'jean_heude_skills'...")
        await qdrant.create_collection(
            collection_name="jean_heude_skills",
            vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
        )

    # 2. Scan et Indexation
    points = []
    for skill_folder in os.listdir(SKILLS_DIR):
        folder_path = os.path.join(SKILLS_DIR, skill_folder)
        manifest_path = os.path.join(folder_path, "manifest.json")
        
        if os.path.isdir(folder_path) and os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            
            # Le texte qui sert à la recherche sémantique : Nom + Description
            text_to_embed = f"{manifest.get('name')} : {manifest.get('description')}"
            vector = await _get_tool_embedding(text_to_embed)
            
            # On génère un ID stable basé sur le nom du dossier pour éviter les doublons
            stable_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, skill_folder))
            
            points.append(models.PointStruct(
                id=stable_id,
                vector=vector,
                payload={"folder": skill_folder, "manifest": manifest}
            ))
    
    if points:
        await qdrant.upsert(collection_name="jean_heude_skills", points=points)
        print(f"🔌 {len(points)} Skills indexés dans Qdrant pour le JIT.")

async def get_relevant_tools(query: str, limit: int = 3, threshold: float = 0.5):
    """Le fameux JIT : Retourne uniquement les outils pertinents, avec un score minimum."""
    try:
        query_vector = await _get_tool_embedding(query)
        
        # NOUVEAU : On ajoute score_threshold pour filtrer les outils hors sujet
        results = await qdrant.query_points(
            collection_name="jean_heude_skills",
            query=query_vector,
            limit=limit,
            score_threshold=threshold  # <--- LE CORRECTIF MAGIQUE EST ICI
        )
        
        tools_list = []
        for hit in results.points:
            # Extraction blindée
            manifest = None
            if hasattr(hit, 'payload') and hit.payload:
                manifest = hit.payload.get("manifest")
            elif isinstance(hit, dict) and "payload" in hit:
                manifest = hit["payload"].get("manifest")
            elif isinstance(hit, tuple):
                for element in hit:
                    if isinstance(element, dict) and "manifest" in element:
                        manifest = element["manifest"]
            
            if manifest:
                tools_list.append({
                    "type": "function",
                    "function": manifest
                })
        
        tool_names = [t["function"]["name"] for t in tools_list]
        print(f"⚡ [JIT] Outils sélectionnés pour cette requête : {tool_names}")
        return tools_list

    except Exception as e:
        print(f"⚠️ Erreur JIT Qdrant: {e}")
        return []

async def call_tool_execution(tool_name: str, arguments: dict):
    """Exécute l'outil (inchangé)."""
    for skill_folder in os.listdir(SKILLS_DIR):
        folder_path = os.path.join(SKILLS_DIR, skill_folder)
        manifest_path = os.path.join(folder_path, "manifest.json")
        
        if os.path.isdir(folder_path) and os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            
            if manifest.get("name") == tool_name:
                script_path = os.path.join(folder_path, "main.py")
                if not os.path.exists(script_path):
                    return f"Erreur: Le script main.py est manquant dans {skill_folder}."
                try:
                    spec = importlib.util.spec_from_file_location(tool_name, script_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    return await module.run(**arguments)
                except Exception as e:
                    return f"Erreur lors de l'exécution du skill {tool_name}: {str(e)}"
    return f"Erreur: Outil '{tool_name}' inconnu."
