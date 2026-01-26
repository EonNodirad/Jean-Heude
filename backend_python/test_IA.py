import pytest
from unittest.mock import patch, MagicMock
from IA import Orchestrator

@pytest.fixture
def mock_client():
    """Simule le client Ollama pour éviter les appels réseau"""
    with patch('IA.client') as mock:
        yield mock

def test_get_local_models(mock_client):
    """Vérifie l'extraction des noms de modèles depuis la réponse Ollama"""
    # 1. On simule la réponse brute de client.list()
    mock_client.list.return_value = {
        'models': [
            {'model': 'phi3:mini', 'details': {}},
            {'model': 'llama3.1:8b', 'details': {}}
        ]
    }
    
    orch = Orchestrator()
    models = orch.get_local_models()
    
    assert len(models) == 2
    assert "phi3:mini" in models
    assert "llama3.1:8b" in models

def test_choose_model_success(mock_client):
    """Vérifie que l'orchestrateur renvoie le modèle choisi par l'IA"""
    mock_client.generate.return_value = {'response': 'llama3.1:8b'}
    
    orch = Orchestrator()
    available = ["phi3:mini", "llama3.1:8b"]
    
    chosen = orch.choose_model("Raconte moi une histoire", available)
    
    assert chosen == "llama3.1:8b"

def test_choose_model_fallback(mock_client):
    """Vérifie le repli (fallback) si l'IA répond n'importe quoi"""
    # L'IA répond un modèle qui n'existe pas dans la liste
    mock_client.generate.return_value = {'response': 'modèle-imaginaire'}
    
    orch = Orchestrator()
    available = ["phi3:mini", "llama3.1:8b"]
    
    # Il doit renvoyer le premier de la liste (available[0])
    chosen = orch.choose_model("Test", available)
    
    assert chosen == "phi3:mini"
