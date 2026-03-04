import os
import json

async def run(skill_name: str, description: str, parameters_schema: str, python_code: str) -> str:
    """Crée dynamiquement un nouvel outil."""
    skill_dir = f"skills/{skill_name}"
    
    # 1. Création du dossier
    os.makedirs(skill_dir, exist_ok=True)
    
    # 2. Nettoyage du JSON des paramètres (au cas où l'IA envoie un string mal formaté)
    try:
        if isinstance(parameters_schema, str):
            params = json.loads(parameters_schema)
        else:
            params = parameters_schema
    except:
        params = {} # Fallback sans paramètres

    # 3. Génération du manifest.json
    manifest = {
        "name": skill_name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": params,
            "required": list(params.keys())
        }
    }
    
    with open(f"{skill_dir}/manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=4, ensure_ascii=False)
        
    # 4. Écriture du code source
    with open(f"{skill_dir}/main.py", "w", encoding="utf-8") as f:
        # On nettoie les éventuelles balises markdown ```python
        clean_code = python_code.replace("```python", "").replace("```", "").strip()
        f.write(clean_code)
        
    return f"✅ L'outil '{skill_name}' a été créé avec succès ! Il sera disponible au prochain redémarrage ou rafraîchissement de tes outils."
