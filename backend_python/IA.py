import ollama
from ollama import Client
from dotenv import load_dotenv

load_dotenv()
remote_host = 'http://192.168.1.49:11434'

client = Client(host=remote_host)

system_message = 'You are a helpful assistant name Jean-Heude'
model_used = 'phi3:mini'
def create_message(message,role):
    return {
        'role' : role,
        'content' : message
    }

def chat(chat_message):
    ollama_response = client.chat(model=model_used, stream=False,messages=chat_message)

    #assistant_message = ''
    #for chunk in ollama_response :
        #assistant_message += chunk['message']['content']
        #print(chunk['message']['content'], end='', flush=True)
    assistant_message = ollama_response['message']['content']
    return assistant_message
    