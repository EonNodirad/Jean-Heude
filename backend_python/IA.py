import os

from ollama import AsyncClient
from dotenv import load_dotenv

load_dotenv()
remote_host = os.getenv("URL_SERVER_OLLAMA")

client = AsyncClient(host=remote_host)

system_message = 'You are a helpful assistant name Jean-Heude'
model_used = 'llama3.1:8b'
def create_message(message,role):
    return {
        'role' : role,
        'content' : message
    }

def chat(chat_message,model_used):
    ollama_response = client.chat(model=model_used, stream=False,messages=chat_message)

    #assistant_message = ''
    #for chunk in ollama_response :
        #assistant_message += chunk['message']['content']
        #print(chunk['message']['content'], end='', flush=True)
    assistant_message = ollama_response['message']['content']
    return assistant_message
    

class Orchestrator:
    def __init__(self):
        # On récupère l'URL depuis l'environnement (Docker ou Local)
        self.remote_host = os.getenv("URL_SERVER_OLLAMA", "http://localhost:11434")
        self.client = AsyncClient(host=self.remote_host)
        # Cache pour éviter de spammer l'API 'show'
        self._capabilities_cache = {}

    async def get_model_details(self, model_name: str):
        """Récupère et cache les capacités techniques d'un modèle."""
        if model_name in self._capabilities_cache:
            return self._capabilities_cache[model_name]

        try:
            info = await self.client.show(model_name)
            # Extraction des capacités depuis l'API officielle (standard 2025/2026)
            caps = info.get("capabilities", [])
            details = info.get("details", {})
            
            data = {
                "name": model_name,
                "can_think": "thinking" in caps,
                "can_use_tools": "tools" in caps,
                "size": details.get("parameter_size", "unknown"),
                "family": details.get("family", "unknown")
            }
            self._capabilities_cache[model_name] = data
            return data
        except Exception as e:
            print(f"⚠️ Erreur d'inspection pour {model_name}: {e}")
            return None

    async def get_local_models(self):
        """Liste tous les modèles locaux installés sur Ollama."""
        try:
            resp = await self.client.list()
            # On vérifie si on a des modèles et on gère les deux formats possibles ('name' ou 'model')
            models = []
            for m in resp.get('models', []):
                # On essaie de récupérer 'model' (format récent) ou 'name' (ancien format)
                name = m.get('model') or m.get('name')
                if name:
                    models.append(name)
            return models
        except Exception as e:
            print(f"❌ Erreur lors de la récupération des modèles: {e}")
            return []

    async def choose_model(self, user_message: str,available_tools):
        """
        Analyse la requête et choisit le cerveau le plus adapté.
        """
        tools = available_tools
        all_models = await self.get_local_models()
        enriched_models = []

        # 1. Filtrage des modèles non-conversationnels
        blacklist = ["embed", "classification", "rerank", "vision"]
        for m in all_models:
            if any(word in m.lower() for word in blacklist):
                continue
            
            details = await self.get_model_details(m)
            if details:
                enriched_models.append(details)

        if not enriched_models:
            return "llama3.1:8b" # Sécurité si aucun modèle trouvé

        # 2. Construction de la "Carte des Modèles" pour le Routeur
        models_map = ""
        for m in enriched_models:
            models_map += f"- {m['name']} | Taille: {m['size']} | Pensée: {m['can_think']} | Outils: {m['can_use_tools']}\n"

        # 3. Prompt de décision
        # On utilise un modèle stable pour la décision (Llama 3.1 8B est parfait pour ça)
        router_model = "llama3.1:8b" 
        
        prompt = f"""
        You are Jean-Heude's orchestrator. 
        Model installed on the PC: {models_map} 
        User question: "{user_message}"
        tool availables : "{tools}"
        Among the installed models, which one is the most suitable to answer ? 
        If needed to use a tools, a model who think it's better
        in other case not necessary to a thinkig model
        You need to choose a model that superior or equal to 7b of paramaters
        Respond ONLY with the exact name of the model, nothing else. """
        

        try:
            response = await self.client.generate(model=router_model, prompt=prompt)
            chosen = response['response'].strip()
            
            # Validation : On s'assure que l'IA n'a pas inventé un nom
            valid_names = [m['name'] for m in enriched_models]
            # On nettoie si l'IA a mis des guillemets ou du texte en trop
            chosen_clean = next((name for name in valid_names if name in chosen), None)
            
            if chosen_clean:
                print(f"🎯 Orchestrateur : Choix de {chosen_clean}")
                return chosen_clean
            
            return valid_names[0] # Fallback
        except Exception:
            return "llama3.1:8b"




