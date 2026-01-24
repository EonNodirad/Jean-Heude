import os

from ollama import Client
from dotenv import load_dotenv

load_dotenv()
remote_host = os.getenv("URL_SERVER_OLLAMA")

client = Client(host=remote_host)

system_message = 'You are a helpful assistant name Jean-Heude'
model_used = 'phi3:mini'
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
    