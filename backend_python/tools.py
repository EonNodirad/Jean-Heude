import yaml
import datetime
import os
import re
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

load_dotenv()
CONFIG_PATH = "mcp_config.yaml"



def load_mcp_config():
    if not os.path.exists(CONFIG_PATH):
        return {"mcp_servers": {}}
    with open(CONFIG_PATH, "r") as f:
        
        content = f.read()
        def replace_env_var(match):
            var_name = match.group(1)
            val = os.getenv(var_name)
            
            if val is None:
                # On utilise sys.stderr pour ne pas polluer le flux JSON-RPC de MCP
                print(f"⚠️ Attention : La variable {var_name} est absente du .env !", file=sys.stderr)
                return f"MISSING_{var_name}"
            
            # 2. CORRECTION DU TYPO : group(0) au lieu de groupe(0)
            return val
        pattern = re.compile(r"\${(\w+)}")
        fixed_content = pattern.sub(replace_env_var, content)
        
        # On parse le YAML final "nettoyé"
        return yaml.safe_load(fixed_content)


async def get_all_tools():
    """Charge dynamiquement TOUS les outils de TOUS les serveurs du YAML"""
    config = load_mcp_config()
    all_tools = []

    # 1. Outil natif
    all_tools.append({
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Donne l'heure et la date actuelle.",
            "parameters": {"type": "object", "properties": {}},
        },
    })

    # 2. Boucle sur les serveurs
    for server_name, srv_config in config.get("mcp_servers", {}).items():
        # ASTUCE : On s'assure que l'environnement force un mode non-interactif
        env = srv_config.get("env", os.environ.copy())
        env["PYTHONUNBUFFERED"] = "1" 

        params = StdioServerParameters(
            command=srv_config["command"],
            args=srv_config["args"],
            env=env
        )
        
        try:
            # On réduit le timeout pour ne pas bloquer tout le démarrage si un serveur est lent
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    for tool in result.tools:
                        all_tools.append({
                            "type": "function",
                            "function": {
                                "name": tool.name,
                                "description": tool.description,
                                "parameters": tool.inputSchema,
                            }
                        })
        except Exception as e:
            # On log l'erreur sur stderr de NOTRE backend pour ne pas polluer l'interface
            print(f"⚠️ Erreur lors de l'initialisation de {server_name}: {e}", file=sys.stderr)

    return all_tools

async def call_tool_execution(name, args):
    """Cherche quel serveur possède l'outil et l'exécute"""
    if name == "get_current_time":
        maintenant = datetime.datetime.now()
        date_longue = maintenant.strftime('%A %d %B %Y, %H:%M:%S')
        return f"Nous sommes le {date_longue}."
    config = load_mcp_config()
    for server_name, srv_config in config.get("mcp_servers", {}).items():
        params = StdioServerParameters(
            command=srv_config["command"],
            args=srv_config["args"],
            env=srv_config.get("env")
        )
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    available_tools = await session.list_tools()
                
                    if any(t.name == name for t in available_tools.tools):
                        # L'outil est trouvé, on l'exécute
                        result = await session.call_tool(name, args)
                        
                        # Extraction propre du texte de réponse
                        if hasattr(result, 'content') and result.content:
                            return result.content[0].text
                        return "L'outil a été exécuté mais n'a renvoyé aucun texte."
        except Exception as e:
            print(f"❌ Erreur sur {server_name} lors de l'exécution de {name}: {e}", file=sys.stderr)
            return f"Désolé, l'outil {name} a rencontré un problème."

    return f"Outil {name} non trouvé sur les serveurs configurés."
