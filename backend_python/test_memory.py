import pytest
from unittest.mock import MagicMock, patch
with patch('os.getenv', side_effect=lambda k, d=None: "http://fake-url" if "URL" in k else d):
    with patch('mem0.Memory.from_config') as mock_mem_init:
        with patch('ollama.Client') as mock_client_init:
            # Maintenant on peut importer sans que ça crash
            from memory import chat_with_memories



def test_config_ollama():
    """ Vérifie que variable environnement charger"""
    import os
    remote_host = os.getenv("URL_SERVER_OLLAMA")
    appelle_IA = os.getenv("APPELLE_SERVER_OLLAMA")

    assert remote_host is not None
    assert appelle_IA is not None

def test_chat_with_dict_memories():
    """Vérifie que la fonction gère bien les mémoires sous forme de dictionnaire (votre elif)"""
    
    # 1. On prépare une fausse mémoire de type dictionnaire
    fake_dict_memories = {
        "results": [
            {"memory": "Jean-Heude adore le café"},
            {"memory": "L'utilisateur est un développeur"}
        ]
    }

    # 2. On configure nos doublures (Mocks)
    # On simule la recherche qui renvoie le dictionnaire
    with patch('memory.memory.search', return_value=fake_dict_memories):
        # On simule la réponse de l'IA
        mock_response = MagicMock()
        mock_response.model_dump.return_value = {
            'message': {'content': "Bonjour ! Je me souviens que vous êtes développeur."}
        }
        
        with patch('memory.client.chat', return_value=mock_response):
            with patch('memory.memory.add'): # On empêche d'écrire en DB
                
                # --- ACTION ---
                resultat = chat_with_memories("Salut !", user_id="noé_test")

                # --- VÉRIFICATION ---
                assert "Bonjour" in resultat
