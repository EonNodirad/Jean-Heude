import sys
import os

# On s'assure de pouvoir importer le module swarm qui est à la racine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from swarm import start_swarm_background

async def run(project_name: str, objective: str, user_id: str = "invite") -> str:
    """Déclenche la création du projet et le recrutement de l'équipe."""
    try:
        # On s'assure que le nom du projet est "propre" pour faire un nom de dossier valide
        clean_project_name = "".join([c if c.isalnum() else "_" for c in project_name])

        print(f"🔴 [Skill delegate_task] Jean-Heude a pressé le bouton ! Lancement du Swarm pour '{clean_project_name}'...")

        # On lance l'orchestrateur (qui va lui-même tourner en arrière-plan)
        resultat = await start_swarm_background(clean_project_name, objective, user_id)

        return resultat
    except Exception as e:
        return f"❌ Erreur lors du lancement de l'équipe : {e}"
