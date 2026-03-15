import os

async def run(file_path: str) -> str:
    """Lit le contenu d'un fichier et le renvoie au LLM."""
    if not os.path.exists(file_path):
        return f"❌ Erreur : Le fichier '{file_path}' n'existe pas sur le disque."
    
    try:
        with open(file_path, mode='r', encoding='utf-8') as f:
            content = f.read()
        return f"--- DÉBUT DE {file_path} ---\n{content}\n--- FIN ---"
    except Exception as e:
        return f"❌ Erreur lors de la lecture du fichier : {str(e)}"
