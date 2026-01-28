import pytest
from unittest.mock import patch, MagicMock
import memory 

@pytest.fixture
def mock_services():
    """Fixture pour simuler mem0, Ollama et l'orchestrateur"""
    with patch('memory.get_memory') as mock_get_memory, \
         patch('memory.client') as mock_ollama, \
         patch('memory.orchestrator') as mock_orch:
        
        # 1. Mock de l'instance de mémoire (mem0)
        mock_mem_instance = MagicMock()
        mock_get_memory.return_value = mock_mem_instance
        
        yield {
            "ollama": mock_ollama,
            "memory": mock_mem_instance,
            "orchestrator": mock_orch
        }

def test_decide_model_logic(mock_services):
    """Vérifie que decide_model choisit bien le modèle et gère le fallback"""
    # Configuration du mock orchestrateur
    mock_services["orchestrator"].get_local_models.return_value = ["phi3:mini", "llama3.1:8b"]
    
    # Cas 1 : Choix normal
    mock_services["orchestrator"].choose_model.return_value = "phi3:mini"
    assert memory.decide_model("Salut") == "phi3:mini"
    
    # Cas 2 : Fallback si 'embed' est renvoyé
    mock_services["orchestrator"].choose_model.return_value = "nomic-embed-text"
    assert memory.decide_model("Cherche un truc") == "llama3.1:8b"

def test_chat_with_list_memories(mock_services):
    """Test le stream avec des mémoires au format LISTE"""
    mock_services["memory"].search.return_value = [{"memory": "Jean-Heude est un robot"}]
    
    # Simulation du Stream Ollama
    mock_services["ollama"].chat.return_value = [
        {'message': {'content': "Je suis "}},
        {'message': {'content': "un robot."}}
    ]

    # ACTION : Note l'ajout du 2ème argument "phi3:mini"
    generator = memory.chat_with_memories("Qui es-tu ?", "phi3:mini")
    reponse_complete = "".join(list(generator))

    assert "Je suis un robot" in reponse_complete
    mock_services["memory"].search.assert_called_once()
    mock_services["memory"].add.assert_called_once()

def test_chat_with_dict_memories(mock_services):
    """Test le stream avec des mémoires au format DICTIONNAIRE"""
    mock_services["memory"].search.return_value = {
        "results": [{"memory": "L'utilisateur aime le bleu"}]
    }
    
    mock_services["ollama"].chat.return_value = [
        {'message': {'content': "Tu aimes "}},
        {'message': {'content': "le bleu."}}
    ]

    # ACTION
    generator = memory.chat_with_memories("Quelle est ma couleur ?", "llama3.1:8b")
    reponse_complete = "".join(list(generator))

    assert "bleu" in reponse_complete

def test_chat_exception_handling(mock_services):
    """Vérifie que les erreurs de connexion sont bien rattrapées (yield error)"""
    mock_services["memory"].search.return_value = []
    # On simule un crash d'Ollama
    mock_services["ollama"].chat.side_effect = Exception("Ollama est hors ligne")

    generator = memory.chat_with_memories("Test", "phi3:mini")
    reponse_complete = "".join(list(generator))

    assert "Erreur de connexion à l'IA" in reponse_complete
