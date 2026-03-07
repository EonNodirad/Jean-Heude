import os
import json
import importlib.util
import uuid
import datetime
import yaml
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from ollama import AsyncClient
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SKILLS_DIR = "skills"

# Connexions locales pour le JIT
qdrant = AsyncQdrantClient(host=os.getenv("URL_QDRANT"), port=6333)
ollama_client = AsyncClient(host=os.getenv("URL_SERVER_OLLAMA"))

# ==========================================
# 🔌 GESTION DES SERVEURS MCP (NOUVEAU)
# ==========================================

def load_mcp_config():
    """Charge la configuration YAML des serveurs MCP."""
    path = "mcp_servers.yaml"
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f).get("mcp_servers", {})

async def get_mcp_tools() -> list:
    """Se connecte dynamiquement aux serveurs MCP pour lister leurs outils."""
    mcp_servers = load_mcp_config()
    all_mcp_tools = []
    
    for server_name, config in mcp_servers.items():
        
        # --- 🛠️ TRADUCTEUR DE VARIABLES D'ENVIRONNEMENT ---
        raw_env = config.get("env", {})
        resolved_env = {}
        for key, value in raw_env.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                # Extrait le nom pur : "${BRAVE_API_KEY}" -> "BRAVE_API_KEY"
                var_name = value[2:-1]
                # Va chercher dans le .env de Python (vide si introuvable)
                resolved_env[key] = os.environ.get(var_name, "")
            else:
                resolved_env[key] = value
        # ---------------------------------------------------

        server_params = StdioServerParameters(
            command=config["command"],
            args=config.get("args", []),
            # On utilise resolved_env ici !
            env={**os.environ, **resolved_env}
        )
        
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools_response = await session.list_tools()
                    
                    for t in tools_response.tools:
                        # 💡 ASTUCE : Préfixe pour savoir vers quel serveur router la commande
                        prefixed_name = f"mcp_{server_name}___{t.name}"
                        all_mcp_tools.append({
                            "type": "function",
                            "function": {
                                "name": prefixed_name,
                                "description": f"[{server_name}] {t.description}",
                                "parameters": t.inputSchema
                            }
                        })
        except Exception as e:
            print(f"❌ [MCP] Impossible de charger le serveur '{server_name}' : {e}")
            
    return all_mcp_tools
# ==========================================
# 🏠 GESTION DES SKILLS LOCAUX (INCHANGÉ)
# ==========================================

async def _get_tool_embedding(text: str):
    """Génère un vecteur pour la description de l'outil."""
    response = await ollama_client.embeddings(model="nomic-embed-text", prompt=text)
    return response["embedding"]

async def sync_skills_to_qdrant():
    """Indexe TOUS les outils (Skills Python + Serveurs MCP) dans Qdrant au démarrage."""
    if not os.path.exists(SKILLS_DIR):
        os.makedirs(SKILLS_DIR)
        
    try:
        await qdrant.delete_collection("jean_heude_skills")
        print("🧹 Nettoyage des anciens skills en mémoire...")
    except Exception:
        pass # Si ça plante, c'est juste qu'elle n'existait pas encore. Pas grave !

    # --- 2. CRÉATION (On reconstruit du neuf) ---
    print("📦 Création de la collection Qdrant 'jean_heude_skills'...")
    await qdrant.create_collection(
        collection_name="jean_heude_skills",
        vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
    )
    try:
        await qdrant.get_collection("jean_heude_knowledge")
    except Exception:
        print("🧠 Création de la mémoire à long terme 'jean_heude_knowledge'...")
        await qdrant.create_collection(
            collection_name="jean_heude_knowledge",
            vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
        )
    points = []
    
    # --- 1. INDEXATION DES SKILLS LOCAUX (PYTHON) ---
    for skill_folder in os.listdir(SKILLS_DIR):
        folder_path = os.path.join(SKILLS_DIR, skill_folder)
        manifest_path = os.path.join(folder_path, "manifest.json")
        
        if os.path.isdir(folder_path) and os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            
            text_to_embed = f"{manifest.get('name')} : {manifest.get('description')}"
            vector = await _get_tool_embedding(text_to_embed)
            stable_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, skill_folder))
            
            points.append(models.PointStruct(
                id=stable_id,
                vector=vector,
                payload={"source": "local", "folder": skill_folder, "manifest": manifest}
            ))

    # --- 2. INDEXATION DES OUTILS MCP (YAML) ---
    print("🔌 Connexion aux serveurs MCP pour indexation...")
    outils_mcp = await get_mcp_tools()
    for outil in outils_mcp:
        manifest = outil["function"]
        text_to_embed = f"{manifest.get('name')} : {manifest.get('description')}"
        vector = await _get_tool_embedding(text_to_embed)
        # On crée un ID unique basé sur le nom préfixé de l'outil MCP
        stable_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, manifest.get('name')))
        
        points.append(models.PointStruct(
            id=stable_id,
            vector=vector,
            payload={"source": "mcp", "manifest": manifest}
        ))

    # --- 3. ENVOI À QDRANT ---
    if points:
        await qdrant.upsert(collection_name="jean_heude_skills", points=points)
        print(f"✅ {len(points)} Outils au total (Locaux + MCP) indexés dans Qdrant !")

async def get_relevant_tools(query: str, limit: int = 5, threshold: float = 0.5):
    """ Qdrant décide de TOUT (Locaux et MCP) et respecte la limite."""
    tools_list = []
    try:
        query_vector = await _get_tool_embedding(query)
        
        # On demande à Qdrant de trouver les meilleurs outils, peu importe leur source !
        results = await qdrant.query_points(
            collection_name="jean_heude_skills",
            query=query_vector,
            limit=limit, # <--- La limite est strictement appliquée ici
            score_threshold=threshold
        )
        
        for hit in results.points:
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
    except Exception as e:
        print(f"⚠️ Erreur JIT Qdrant: {e}")

    tool_names = [t["function"]["name"] for t in tools_list]
    print(f"⚡ [JIT Unifié] Outils sélectionnés par l'IA ({len(tools_list)}/{limit}) : {tool_names}")
    return tools_list

async def call_tool_execution(tool_name: str, arguments: dict):
    """Exécute l'outil (Route MCP ou Route Locale)."""
    
    # 🌐 ROUTE 1 : C'est un outil MCP !
    if tool_name.startswith("mcp_"):
        parts = tool_name.split("___")
        server_name = parts[0].replace("mcp_", "")
        real_tool_name = parts[1]
        
        config = load_mcp_config().get(server_name)
        if not config:
            return f"❌ Erreur : Le serveur MCP '{server_name}' n'existe plus dans le YAML."
            
        raw_env = config.get("env", {})
        resolved_env = {}
        for key, value in raw_env.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                var_name = value[2:-1] 
                resolved_env[key] = os.environ.get(var_name, "")
            else:
                resolved_env[key] = value
                
        server_params = StdioServerParameters(
            command=config["command"],
            args=config.get("args", []),
            # Toujours resolved_env ici
            env={**os.environ, **resolved_env}
        )
        
        print(f"🔌 [MCP] Exécution de {real_tool_name} sur le serveur {server_name}...")
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(real_tool_name, arguments)
                    
                    if result.content and len(result.content) > 0:
                        texte_resultat = result.content[0].text
                        
                        # ==========================================
                        # 🧠 L'INTERCEPTEUR DE MÉMOIRE (AUTO-CACHE)
                        # ==========================================
                        if server_name in ["brave-search", "world_monitor", "puppeteer", "meteo"]:
                            try:
                                print(f"💾 [Auto-Cache] Enregistrement du savoir depuis '{server_name}'...")
                                date_actuelle = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                
                                # On limite la taille pour ne pas saturer le vecteur Qdrant (1500 caractères)
                                extrait = texte_resultat[:1500] 
                                texte_a_memoriser = f"Date de l'info: {date_actuelle} | Source: {server_name} | Requête: {arguments} | Contenu: {extrait}"
                                
                                # 1. On vectorise le texte
                                vector = await _get_tool_embedding(texte_a_memoriser)
                                
                                # 2. On l'envoie silencieusement dans Qdrant
                                await qdrant.upsert(
                                    collection_name="jean_heude_knowledge",
                                    points=[models.PointStruct(
                                        id=str(uuid.uuid4()), 
                                        vector=vector, 
                                        payload={
                                            "source": server_name, 
                                            "date": date_actuelle, 
                                            "contenu": texte_a_memoriser
                                        }
                                    )]
                                )
                                print("✅ [Auto-Cache] Savoir stocké pour l'éternité !")
                            except Exception as mem_err:
                                print(f"⚠️ Erreur lors de la mémorisation automatique : {mem_err}")

                        # On n'oublie pas de renvoyer le texte à Jean-Heude pour qu'il puisse répondre !
                        return texte_resultat
                        
                    return "✅ Outil MCP exécuté avec succès (pas de retour texte)."
        except Exception as e:
            return f"❌ Erreur d'exécution MCP : {e}"

    # 🏠 ROUTE 2 : C'est un Skill local !
    else:
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
