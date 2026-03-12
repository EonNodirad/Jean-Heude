import os
import json
import importlib.util
import uuid
import datetime
import asyncio
import logging
import yaml
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from ollama import AsyncClient
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import inspect

SKILLS_DIR = "skills"
MCP_CONNECT_TIMEOUT = 10   # secondes pour établir la connexion MCP
MCP_TOOL_TIMEOUT = 30      # secondes pour l'exécution d'un outil MCP

logger = logging.getLogger("jean_heude.tools")

# Connexions locales pour le JIT
qdrant = AsyncQdrantClient(host=os.getenv("URL_QDRANT"), port=6333)
ollama_client = AsyncClient(host=os.getenv("URL_SERVER_OLLAMA"))

# ==========================================
# 🔌 GESTION DES SERVEURS MCP (NOUVEAU)
# ==========================================

def load_mcp_config():
    """Charge la configuration YAML et résout les chemins relatifs dynamiquement."""
    path = "mcp_servers.yaml"
    if not os.path.exists(path):
        return {}
        
    with open(path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)
        mcp_servers = config_data.get("mcp_servers", {})

    # 🎯 RÉSOLUTION DYNAMIQUE DES CHEMINS
    # Récupère le dossier absolu où se trouve mcp_servers.yaml (ex: /app ou C:\Projet)
    base_dir = os.path.dirname(os.path.abspath(path))

    for server_name, config in mcp_servers.items():
        if "args" in config and isinstance(config["args"], list):
            new_args = []
            for arg in config["args"]:
                # Si l'argument est un chemin relatif commençant par ./
                if isinstance(arg, str) and arg.startswith("./"):
                    # On le transforme en chemin absolu basé sur l'emplacement du YAML
                    abs_path = os.path.normpath(os.path.join(base_dir, arg))
                    new_args.append(abs_path)
                else:
                    new_args.append(arg)
            config["args"] = new_args
            
    return mcp_servers

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
            async with asyncio.timeout(MCP_CONNECT_TIMEOUT):
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools_response = await session.list_tools()

                        for t in tools_response.tools:
                            prefixed_name = f"mcp_{server_name}___{t.name}"
                            all_mcp_tools.append({
                                "type": "function",
                                "function": {
                                    "name": prefixed_name,
                                    "description": f"[{server_name}] {t.description}",
                                    "parameters": t.inputSchema
                                }
                            })
        except asyncio.TimeoutError:
            logger.warning("[MCP] Timeout lors du chargement du serveur '%s'.", server_name)
        except Exception as e:
            logger.error("[MCP] Impossible de charger le serveur '%s' : %s", server_name, e)
            
    return all_mcp_tools
# ==========================================
# 🏠 GESTION DES SKILLS LOCAUX (INCHANGÉ)
# ==========================================

async def _get_tool_embedding(text: str):
    """Génère un vecteur pour la description de l'outil."""
    try:
        response = await ollama_client.embeddings(model="nomic-embed-text", prompt=text)
        return response["embedding"]
    except Exception as e:
        logger.warning("[Ollama] Impossible de générer l'embedding (Serveur hors ligne ?) : %s", e)
        return None

async def sync_skills_to_qdrant():
    """Indexe TOUS les outils (Skills Python + Serveurs MCP) dans Qdrant au démarrage."""
    if not os.path.exists(SKILLS_DIR):
        os.makedirs(SKILLS_DIR)

    try:
        await qdrant.delete_collection("jean_heude_skills")
        logger.info("Nettoyage des anciens skills en mémoire.")
    except Exception as e:
        logger.debug("Suppression 'jean_heude_skills' ignorée : %s", e)

    logger.info("Création de la collection Qdrant 'jean_heude_skills'...")
    try:
        await qdrant.create_collection(
            collection_name="jean_heude_skills",
            vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
        )
    except Exception as e:
        if "already exists" in str(e).lower():
            logger.warning("Collection 'jean_heude_skills' déjà existante, suppression forcée et recréation.")
            await qdrant.delete_collection("jean_heude_skills")
            await qdrant.create_collection(
                collection_name="jean_heude_skills",
                vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
            )
        else:
            raise
    try:
        await qdrant.get_collection("jean_heude_knowledge")
    except Exception:
        logger.info("Création de la mémoire à long terme 'jean_heude_knowledge'...")
        await qdrant.create_collection(
            collection_name="jean_heude_knowledge",
            vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
        )
    points = []

    for skill_folder in os.listdir(SKILLS_DIR):
        folder_path = os.path.join(SKILLS_DIR, skill_folder)
        manifest_path = os.path.join(folder_path, "manifest.json")

        if os.path.isdir(folder_path) and os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            text_to_embed = f"{manifest.get('name')} : {manifest.get('description')}"
            vector = await _get_tool_embedding(text_to_embed)
            if not vector:
                logger.warning("Impossible d'indexer le skill local '%s' : embeddings indisponibles.", skill_folder)
                continue

            stable_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, skill_folder))

            points.append(models.PointStruct(
                id=stable_id,
                vector=vector,
                payload={"source": "local", "folder": skill_folder, "manifest": manifest}
            ))

    logger.info("Connexion aux serveurs MCP pour indexation...")
    outils_mcp = await get_mcp_tools()
    for outil in outils_mcp:
        manifest = outil["function"]
        text_to_embed = f"{manifest.get('name')} : {manifest.get('description')}"
        vector = await _get_tool_embedding(text_to_embed)
        if not vector:
            logger.warning("Impossible d'indexer l'outil MCP '%s' : embeddings indisponibles.", manifest.get('name'))
            continue

        stable_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, manifest.get('name')))

        points.append(models.PointStruct(
            id=stable_id,
            vector=vector,
            payload={"source": "mcp", "manifest": manifest}
        ))

    if points:
        await qdrant.upsert(collection_name="jean_heude_skills", points=points)
        logger.info("%d outils (Locaux + MCP) indexés dans Qdrant.", len(points))

async def get_relevant_tools(query: str, limit: int = 5, threshold: float = 0.5):
    """ Qdrant décide de TOUT (Locaux et MCP) et respecte la limite."""
    tools_list = []
    try:
        query_vector = await _get_tool_embedding(query)
        if not query_vector:
            logger.warning("Impossible de chercher des outils pertinents : embeddings indisponibles.")
            return tools_list
        
        # On demande à Qdrant de trouver les meilleurs outils, peu importe leur source !
        results = await qdrant.query_points(
            collection_name="jean_heude_skills",
            query=query_vector,
            limit=limit, # <--- La limite est strictement appliquée ici
            score_threshold=threshold
        )
        
        for hit in results.points:
            manifest = None
            
            # Extraction sûre : on récupère le payload s'il existe, sinon None
            payload = getattr(hit, "payload", None)
            
            # Si le payload est bien un dictionnaire, on extrait le manifest
            if isinstance(payload, dict):
                manifest = payload.get("manifest")
            # Fallback de sécurité au cas où Qdrant renvoie un dictionnaire direct
            elif isinstance(hit, dict) and "payload" in hit:
                manifest = hit["payload"].get("manifest")
            
            if manifest:
                tools_list.append({
                    "type": "function",
                    "function": manifest
                })
    except Exception as e:
        logger.warning("Erreur JIT Qdrant: %s", e)

    tool_names = [t["function"]["name"] for t in tools_list]
    logger.info("[JIT] Outils sélectionnés (%d/%d) : %s", len(tools_list), limit, tool_names)
    return tools_list

# 👤 AJOUT du paramètre user_id avec "invite" par défaut
async def call_tool_execution(tool_name: str, arguments: dict, user_id: str = "invite"):
    """Exécute l'outil (Route MCP ou Route Locale)."""
    
    # 🌐 ROUTE 1 : C'est un outil MCP !
    if tool_name.startswith("mcp_"):
        parts = tool_name.split("___")
        server_name = parts[0].replace("mcp_", "")
        real_tool_name = parts[1]
        
        # ✅ Utilise load_mcp_config() qui a maintenant les chemins résolus !
        mcp_config = load_mcp_config()
        config = mcp_config.get(server_name)
        
        if not config:
            return f"❌ Erreur : Le serveur MCP '{server_name}' n'existe plus."
            
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
            env={**os.environ, **resolved_env}
        )
        
        logger.info("[MCP] Exécution de %s sur le serveur %s...", real_tool_name, server_name)
        try:
            async with asyncio.timeout(MCP_TOOL_TIMEOUT):
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(real_tool_name, arguments)

                        if result.content:
                            texte_resultat = ""
                            for block in result.content:
                                if getattr(block, "type", "") == "text":
                                    contenu_texte = getattr(block, "text", "")
                                    texte_resultat += str(contenu_texte)

                            if texte_resultat:
                            # ==========================================
                            # 🧠 L'INTERCEPTEUR DE MÉMOIRE (AUTO-CACHE GLOBAL)
                            # ==========================================
                                if server_name in ["brave-search", "world_monitor", "puppeteer", "meteo"]:
                                    try:
                                        logger.info("[Auto-Cache] Enregistrement du savoir depuis '%s'...", server_name)
                                        date_actuelle = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                                        extrait = texte_resultat[:1500]
                                        texte_a_memoriser = f"Date de l'info: {date_actuelle} | Source: {server_name} | Requête: {arguments} | Contenu: {extrait}"

                                        vector = await _get_tool_embedding(texte_a_memoriser)
                                        if not vector:
                                            raise ValueError("Embedding indisponible")

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
                                        logger.info("[Auto-Cache] Savoir Universel stocké.")
                                    except Exception as mem_err:
                                        logger.warning("Erreur lors de la mémorisation automatique : %s", mem_err)

                            return texte_resultat

                        return "✅ Outil MCP exécuté avec succès (pas de retour texte)."
        except asyncio.TimeoutError:
            return f"❌ Timeout ({MCP_TOOL_TIMEOUT}s) lors de l'exécution de '{real_tool_name}'."
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
                        # Le garde-fou pour Pyright :
                        if spec is None or spec.loader is None:
                            return f"Erreur: Impossible d'initialiser le module {tool_name}."
                            
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        # 🪄 INJECTION MAGIQUE DU USER_ID POUR LES OUTILS LOCAUX
                        if hasattr(module, "run"):
                            sig = inspect.signature(module.run)
                            # Si le développeur a mis "user_id" dans les paramètres de son outil, on lui donne !
                            if "user_id" in sig.parameters:
                                arguments["user_id"] = user_id
                                
                        return await module.run(**arguments)
                    except Exception as e:
                        return f"Erreur lors de l'exécution du skill {tool_name}: {str(e)}"
        
        return f"Erreur: Outil '{tool_name}' inconnu."
