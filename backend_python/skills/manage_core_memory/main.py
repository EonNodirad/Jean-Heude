import os
import sys

# 1. On indique à Python où se trouve la racine du projet (deux dossiers plus haut)
chemin_racine = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
if chemin_racine not in sys.path:
    sys.path.append(chemin_racine)

# 2. Maintenant Python sait trouver ton fichier memory.py !
import memory

async def run(action: str, content: str = "") -> str:
    """Gère le fichier MEMORY.md de Jean-Heude."""
    file_path = "memory/MEMORY.md"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # 1. Sécurité : On s'assure que le fichier existe
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("# Mémoire Long Terme de Jean-Heude\n\n")

    # 2. LECTURE
    if action == "read":
        with open(file_path, "r", encoding="utf-8") as f:
            memoire = f.read()
            if not memoire.strip():
                return "Ta mémoire est actuellement vide."
            return f"Voici le contenu de ton ADN (MEMORY.md) :\n{memoire}"
            
    # 3. AJOUT
    elif action == "append":
        if not content:
            return "❌ Erreur : Tu dois fournir un 'content' pour ajouter une mémoire."
            
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"- {content}\n")
        
        # 🟢 Appel direct à ta fonction de synchronisation !
        await memory.sync_memory_md()
        return f"✅ L'information '{content}' a été gravée dans ta mémoire à long terme."
        
    # 4. SUPPRESSION
    elif action == "delete_keyword":
        if not content or len(content) < 3:
            return "❌ Erreur : Fournis un mot-clé précis (min 3 lettres) pour éviter de tout supprimer par erreur."
            
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        # On garde toutes les lignes qui NE CONTIENNENT PAS le mot-clé
        new_lines = [line for line in lines if content.lower() not in line.lower()]
        lignes_supprimees = len(lines) - len(new_lines)
        
        if lignes_supprimees == 0:
            return f"⚠️ Aucun souvenir contenant le mot '{content}' n'a été trouvé."
            
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
            
        # 🟢 Appel direct à ta fonction de synchronisation !
        await memory.sync_memory_md()
        return f"✅ {lignes_supprimees} souvenir(s) contenant '{content}' ont été effacés de ta mémoire."
        
    return "❌ Action non reconnue. Utilise 'read', 'append', ou 'delete_keyword'."
