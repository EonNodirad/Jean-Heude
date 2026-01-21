from qdrant_client import QdrantClient

# Connexion à ton Qdrant local
client = QdrantClient(host="localhost", port=6333)

collection_name = "mem0"

try:
    client.delete_collection(collection_name=collection_name)
    print(f"✅ SUCCÈS : La collection '{collection_name}' a été pulvérisée.")
    print("Maintenant, Qdrant est tout propre.")
except Exception as e:
    print(f"❌ ERREUR : Impossible de supprimer (elle n'existe peut-être déjà plus) : {e}")
