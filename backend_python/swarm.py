import os
import json
import asyncio
import re

# On importe ton infrastructure souveraine !
import memory
import tools
from ollama import AsyncClient

ADMIN_MODEL = "llama3.1:8b" # Modèle fixe juste pour le recrutement DRH
ollama_client = AsyncClient(host=os.getenv("URL_SERVER_OLLAMA"))

class NativeSwarm:
    def __init__(self, project_name: str, objective: str):
        self.project_name = project_name
        self.objective = objective
        self.workspace = f"memory/projects/{project_name}"
        self.context_file = f"{self.workspace}/shared_context.md"
        os.makedirs(self.workspace, exist_ok=True)

    async def _recruit_team(self) -> list:
        """Phase 1 : Le recrutement en JSON par le DRH."""
        print(f"👔 [Swarm] Analyse du projet '{self.project_name}' et recrutement...")
        
        prompt = f"""Tu es l'Orchestrateur d'une équipe d'IA.
Objectif du projet : "{self.objective}"

Crée l'équipe séquentielle parfaite pour accomplir cela.
Renvoie UNIQUEMENT un objet JSON valide :
{{
  "team": [
    {{
      "name": "Nom du rôle",
      "system_prompt": "Le prompt strict pour cet agent.",
      "task": "La mission exacte de cet agent."
    }}
  ]
}}"""
        response = await ollama_client.chat(
            model=ADMIN_MODEL,
            messages=[{"role": "user", "content": prompt}],
            format="json"
        )
        try:
            team = json.loads(response.message.content).get("team", [])
            print(f"👥 Équipe prête : {', '.join([a['name'] for a in team])}")
            return team
        except Exception as e:
            print(f"❌ Erreur de recrutement : {e}")
            return []

    async def _run_sub_agent(self, agent: dict, current_context: str) -> str:
        """Phase 2 : L'agent travaille en utilisant TON moteur memory.py (avec ses outils !)"""
        print(f"\n🚀 Lancement du sous-agent : {agent['name']}")
        
        prompt_mission = f"Objectif global: {self.objective}\n\nContexte actuel:\n{current_context}\n\nTa mission immédiate: {agent['task']}"
        
        messages = [
            {"role": "system", "content": agent['system_prompt']},
            {"role": "user", "content": prompt_mission}
        ]
        
        # 1. Ton orchestrateur choisit le meilleur modèle pour CET agent !
        chosen_model = await memory.decide_model(prompt_mission)
        
        # 2. Ton moteur charge les outils pertinents pour CET agent !
        relevant_tools = await tools.get_relevant_tools(prompt_mission, limit=5)
        
        # 3. On lance LA BOUCLE AGENTIQUE (en mute pour ne pas spammer le TTS de Jean-Heude)
        final_text = ""
        async for chunk in memory.execute_agent_loop(messages, chosen_model, relevant_tools, mute_audio=True):
            # On nettoie la pensée (¶) et l'audio pour garder juste le rapport de l'agent
            clean_chunk = re.sub(r'\|\|AUDIO_ID:.*?\|\|', '', chunk)
            if not clean_chunk.startswith("¶"):
                final_text += clean_chunk
                
        return final_text.strip()

    async def launch(self):
        """Démarre la chaîne."""
        team = await self._recruit_team()
        if not team:
            return "Échec du recrutement."

        current_context = f"Le dossier de travail est {self.workspace}. Aucun fichier n'a encore été créé."
        with open(self.context_file, "w", encoding="utf-8") as f:
            f.write(f"# Projet : {self.project_name}\nObjectif : {self.objective}\n\n")

        for agent in team:
            # L'agent s'exécute avec tes outils
            result = await self._run_sub_agent(agent, current_context)
            
            # On nettoie la balise <think> du rapport pour le contexte partagé
            clean_result = re.sub(r'<think>.*?(</think>|$)', '', result, flags=re.DOTALL).strip()
            
            current_context += f"\n\n--- Rapport de {agent['name']} ---\n{clean_result}"
            
            with open(self.context_file, "a", encoding="utf-8") as f:
                f.write(f"## {agent['name']}\n**Mission:** {agent['task']}\n\n{clean_result}\n\n")

        print(f"🏁 [Swarm] Projet '{self.project_name}' terminé ! Dossier : {self.workspace}")

# --- Le point d'entrée pour Jean-Heude ---
async def start_swarm_background(project_name: str, objective: str):
    """Lance le Swarm sans bloquer le main thread."""
    swarm = NativeSwarm(project_name, objective)
    asyncio.create_task(swarm.launch())
    return f"✅ C'est lancé. J'ai créé le projet '{project_name}' et l'équipe travaille dessus en arrière-plan. Le résultat sera dans memory/projects/{project_name}."
