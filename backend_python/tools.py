import yaml
import datetime
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

CONFIG_PATH = "mcp_config.yaml"

def load_mcp_config():
    if not os.path.exists(CONFIG_PATH):
        return {"mcp_servers": {}}
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

async def get_all_tools():
    """Charge dynamiquement TOUS les outils de TOUS les serveurs du YAML"""
    config = load_mcp_config()
    all_tools = []

    # 1. On garde toujours notre petit outil natif pour l'heure
    all_tools.append({
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Donne l'heure et la date actuelle.",
            "parameters": {"type": "object", "properties": {}},
        },
    })

    # 2. On boucle sur chaque serveur défini dans le YAML
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
                    result = await session.list_tools()
                    for tool in result.tools:
                        all_tools.append({
                            "type": "function",
                            "function": {
                                "name": tool.name, # ex: read_file
                                "description": tool.description,
                                "parameters": tool.inputSchema,
                            }
                        })
        except Exception as e:
            if hasattr(e, 'exceptions'):
                for sub_e in e.exceptions:
                    print(f"❌ Sous-erreur MCP : {sub_e}")
            else:
                print(f"⚠️ Erreur MCP : {e}")

    return all_tools

async def call_tool_execution(name, args):
    """Cherche quel serveur possède l'outil et l'exécute"""
    if name == "get_current_time":
        return f"Il est {datetime.datetime.now().strftime('%H:%M:%S')}."

    # On doit retrouver quel serveur a cet outil
    config = load_mcp_config()
    for server_name, srv_config in config.get("mcp_servers", {}).items():
        params = StdioServerParameters(
            command=srv_config["command"],
            args=srv_config["args"],
            env=srv_config.get("env")
        )
        try:
        # On vérifie si l'outil appartient à ce serveur
        # Note : Dans une version pro, on garderait les sessions ouvertes pour aller plus vite
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    available_tools = await session.list_tools()
                
                    if any(t.name == name for t in available_tools.tools):
                        result = await session.call_tool(name, args)
                        return result.content[0].text if result.content else "Pas de réponse."
        except Exception as e:
            # ICI : On affiche l'erreur réelle dans les logs du serveur
            print(f"❌ Erreur CRITIQUE sur le serveur MCP {server_name} : {type(e).__name__} - {e}")
            return f"Désolé, l'outil {name} a rencontré un problème technique."
