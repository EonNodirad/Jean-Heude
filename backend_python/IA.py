import os

from ollama import Client
from dotenv import load_dotenv

load_dotenv()
remote_host = os.getenv("URL_SERVER_OLLAMA")

client = Client(host=remote_host)

system_message = 'You are a helpful assistant name Jean-Heude'
model_used = 'Prodoc/intent-classification-1b'
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
    

class Orchestrator :
    def __init__(self):
        self.manager_model = model_used

    def get_local_models(self):
        model_info = client.list()
        return [m['model'] for m in model_info['models']]
    
    def choose_model(self, user_prompt, available_models):
        models = available_models
        if not available_models:
            models = "phi3:mini"
        dispatch_prompt = f"""
        You are Jean-Heude's orchestrator. 
        Model installed on the PC: {models} 
        User question: "{user_prompt}"
        Among the installed models, which one is the most suitable to answer ? 
        Respond ONLY with the exact name of the model, nothing else. 
        """

        response = client.generate(model=self.manager_model,prompt= dispatch_prompt)
        chosen = response['response'].strip()

        return chosen if chosen in available_models else available_models[0]

