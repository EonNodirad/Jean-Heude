import pytest
from unittest.mock import patch, MagicMock
import memory  # Ton fichier


@pytest.fixture
def mock_services():
    """Fixture pour simuler les composants externes et la mémoire vive"""
    with patch('memory.get_memory') as mock_get_memory, \
         patch('memory.client') as mock_ollama, \
         patch('memory.orchestrator') as mock_orch:
        
        # 1. On crée un objet simulé pour la classe Memory de mem0
        mock_mem_instance = MagicMock()
        mock_list_models = ["phi3:mini", "llama3.1:8b"]
        # On force get_memory() à renvoyer cet objet simulé
        mock_get_memory.return_value = (mock_mem_instance, mock_list_models)
        
        # 2. Simulation de l'orchestrateur (évite le crash list index out of range)
        mock_orch.choose_model.return_value = "phi3:mini"
        
        yield {
            "ollama": mock_ollama,
            "memory": mock_mem_instance, # C'est notre instance simulée
            "orchestrator": mock_orch
        }

def test_chat_with_list_memories(mock_services):
    """Test le cas où mem0 renvoie une LISTE"""
    # 1. Configurer la mémoire simulée (format liste)
    mock_services["memory"].search.return_value = [
        {"memory": "Jean-Heude est un robot"}
    ]
    
    # 2. Configurer la réponse de l'IA (Ollama)
    mock_response = MagicMock()
    # On simule la structure de l'objet renvoyé par le client Ollama
    mock_response.model_dump.return_value = {
        'message': {'content': "Je suis un robot."}
    }
    mock_services["ollama"].chat.return_value = mock_response

    # Action
    reponse = memory.chat_with_memories("Qui es-tu ?")

    # Vérifications
    assert "Je suis un robot" in reponse
    # On vérifie que la méthode search de NOTRE instance simulée a été appelée
    mock_services["memory"].search.assert_called_once()
    # On vérifie qu'on a bien tenté d'ajouter la conversation en mémoire
    mock_services["memory"].add.assert_called_once()

def test_chat_with_dict_memories(mock_services):
    """Test le cas où mem0 renvoie un DICT (ton fameux elif)"""
    # 1. Format Dictionnaire avec 'results'
    mock_services["memory"].search.return_value = {
        "results": [{"memory": "L'utilisateur aime le bleu"}]
    }
    
    mock_response = MagicMock()
    mock_response.model_dump.return_value = {
        'message': {'content': "Tu aimes le bleu."}
    }
    mock_services["ollama"].chat.return_value = mock_response
    mock_services["orchestrator"].choose_model.return_value = "phi3:mini"

    reponse = memory.chat_with_memories("Quelle est ma couleur préférée ?")

    assert "bleu" in reponse

def test_chat_model_fallback(mock_services):
    """Vérifie que si l'orchestrateur choisit un modèle 'embed', on bascule sur llama"""
    mock_services["memory"].search.return_value = []
    mock_services["orchestrator"].choose_model.return_value = "nomic-embed-text"
    
    mock_response = MagicMock()
    mock_response.model_dump.return_value = {'message': {'content': 'ok'}}
    mock_services["ollama"].chat.return_value = mock_response

    memory.chat_with_memories("test")
    
    # Vérifie que ollama.chat a été appelé avec llama3.1:8b à cause du fallback
    args, kwargs = mock_services["ollama"].chat.call_args
    assert kwargs['model'] == "llama3.1:8b"
