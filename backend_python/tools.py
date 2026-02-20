import os
import json
import importlib.util

SKILLS_DIR = "skills"

async def get_all_tools():
    """
    Scanne le dossier /skills et retourne les schémas pour Ollama.
    Pour l'instant, on charge tout (On ajoutera le JIT juste après).
    """
    tools_list = []
    
    if not os.path.exists(SKILLS_DIR):
        os.makedirs(SKILLS_DIR)
        print("📁 Dossier /skills créé. Ajoute des plugins communautaires ici !")
        return tools_list

    for skill_folder in os.listdir(SKILLS_DIR):
        folder_path = os.path.join(SKILLS_DIR, skill_folder)
        manifest_path = os.path.join(folder_path, "manifest.json")
        
        if os.path.isdir(folder_path) and os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                    # On le formate pour l'API standard d'Ollama/OpenAI
                    tools_list.append({
                        "type": "function",
                        "function": manifest
                    })
            except Exception as e:
                print(f"⚠️ Erreur de chargement du manifest pour {skill_folder}: {e}")
                
    return tools_list

async def call_tool_execution(tool_name: str, arguments: dict):
    """
    Trouve le bon dossier, charge son fichier main.py en mémoire,
    et exécute sa fonction principale (run).
    """
    for skill_folder in os.listdir(SKILLS_DIR):
        folder_path = os.path.join(SKILLS_DIR, skill_folder)
        manifest_path = os.path.join(folder_path, "manifest.json")
        
        if os.path.isdir(folder_path) and os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            
            # Si c'est l'outil demandé par l'IA
            if manifest.get("name") == tool_name:
                script_path = os.path.join(folder_path, "main.py")
                
                if not os.path.exists(script_path):
                    return f"Erreur: Le script main.py est manquant dans {skill_folder}."
                
                try:
                    # Chargement magique (dynamique) du script Python
                    spec = importlib.util.spec_from_file_location(tool_name, script_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # On suppose que chaque module communautaire a une fonction async run()
                    return await module.run(**arguments)
                    
                except Exception as e:
                    return f"Erreur lors de l'exécution du skill {tool_name}: {str(e)}"
    
    return f"Erreur: Outil '{tool_name}' inconnu ou non installé."
