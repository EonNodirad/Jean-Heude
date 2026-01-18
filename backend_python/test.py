from ollama import Client
client = Client(host='http://192.168.1.49:11434')
print(client.list()) # Cela doit afficher la liste des modèles de l'AUTRE ordi
