import os
import yaml

async def run(server_name: str, command: str, args: list, env: dict = None) -> str:
    """Ajoute un serveur MCP existant directement dans la configuration YAML."""
    
    # On remonte à la racine du projet pour trouver le YAML de manière sécurisée
    dossier_actuel = os.path.dirname(os.path.abspath(__file__))
    racine_projet = os.path.abspath(os.path.join(dossier_actuel, "..", ".."))
    yaml_path = os.path.join(racine_projet, "mcp_servers.yaml")
    
    # Lecture du YAML existant
    if os.path.exists(yaml_path):
        with open(yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}
        
    if "mcp_servers" not in config:
        config["mcp_servers"] = {}
        
    # Préparation de la nouvelle configuration
    new_server_config = {
        "command": command,
        "args": args
    }
    
    # On ajoute l'environnement s'il y en a un (sans écraser avec un dict vide si inutile)
    if env and isinstance(env, dict) and len(env) > 0:
        new_server_config["env"] = env
        
    # Injection dans le dictionnaire
    config["mcp_servers"][server_name] = new_server_config
    
    # Sauvegarde
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
    return f"✅ Succès ! Le serveur MCP '{server_name}' a été ajouté au YAML. Le système Auto-Watch va le détecter et l'indexer dans la seconde."
