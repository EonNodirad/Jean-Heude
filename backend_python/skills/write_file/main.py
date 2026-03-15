import os

async def run(file_path: str, content: str) -> str:
    """Écrit le contenu dans le fichier spécifié, en créant les dossiers si besoin."""
    # S'assure que le dossier parent existe (ex: memory/projects/)
    dossier = os.path.dirname(file_path)
    if dossier:
        os.makedirs(dossier, exist_ok=True)
        
    try:
        with open(file_path, mode='w', encoding='utf-8') as f:
            f.write(content)
        return f"✅ Succès : Le fichier '{file_path}' a été enregistré et mis à jour."
    except Exception as e:
        return f"❌ Erreur lors de l'écriture du fichier : {str(e)}"
