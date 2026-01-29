import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
import memory 

# Configuration du comportement d'Ollama pour simuler l'Agent
async def smart_ollama_mock(*args, **kwargs):
    """
    Simule Ollama : 
    - Si stream=False (par défaut pour les outils) -> Renvoie un Dict.
    - Si stream=True (pour la réponse finale) -> Renvoie un Générateur.
    """
    if kwargs.get('stream'):
        async def gen():
            yield {'message': {'content': "Voici la "}}
            yield {'message': {'content': "réponse finale."}}
        return gen()
    
    # Simule une demande d'outil (Sequential Thinking)
    return {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "call_123",
                "function": {
                    "name": "sequential_thinking",
                    "arguments": json.dumps({"thought": "Je réfléchis..."})
                }
            }]
        }
    }

@pytest.fixture
def mock_services():
    """Fixture pour isoler les services externes"""
    with patch('memory.get_memory') as mock_get_memory, \
         patch('memory.client', new_callable=AsyncMock) as mock_ollama, \
         patch('memory.orchestrator') as mock_orch, \
         patch('memory.tools.get_all_tools', new_callable=AsyncMock) as mock_get_tools, \
         patch('memory.tools.call_tool_execution', new_callable=AsyncMock) as mock_exec:
        
        # Mock de la base de données de mémoire
        mock_mem_instance = MagicMock()
        mock_get_memory.return_value = mock_mem_instance
        
        # Mock des outils disponibles
        mock_get_tools.return_value = [{"function": {"name": "sequential_thinking", "parameters": {}}}]
        mock_exec.return_value = "Analyse effectuée avec succès."

        yield {
            "ollama": mock_ollama,
            "memory": mock_mem_instance,
            "orchestrator": mock_orch,
            "exec": mock_exec
        }

# --- TESTS ---

def test_decide_model_logic(mock_services):
    """Vérifie le choix du modèle et le fallback"""
    mock_services["orchestrator"].get_local_models.return_value = ["phi3:mini", "llama3.1:8b"]
    mock_services["orchestrator"].choose_model.return_value = "phi3:mini"
    assert memory.decide_model("Salut") == "phi3:mini"

@pytest.mark.asyncio
async def test_chat_with_agent_logic(mock_services):
    """
    Test le flux complet :
    1. Appel 1 : L'IA demande l'outil
    2. Appel 2 : L'IA voit le résultat et dit 'C'est bon, j'ai fini' (pas d'outil)
    3. Appel 3 : L'IA génère le stream final
    """
    mock_services["memory"].search.return_value = []

    # 1. On prépare le générateur pour la fin
    async def final_stream():
        yield {'message': {'content': "Voici la "}}
        yield {'message': {'content': "réponse finale."}}

    # 2. On définit la séquence exacte de ce qu'Ollama renvoie
    mock_services["ollama"].chat.side_effect = [
        # Premier passage dans la boucle (i=0) : Demande d'outil
        {
            "message": {
                "role": "assistant",
                "tool_calls": [{"id": "1", "function": {"name": "sequential_thinking", "arguments": "{}"}}]
            }
        },
        # Deuxième passage (i=1) : L'IA a fini avec les outils (renvoie un msg vide sans tool_calls)
        {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": None # C'est CA qui déclenche le 'else' dans ton code
            }
        },
        # Appel final (le stream)
        final_stream()
    ]

    reponse_complete = ""
    async for chunk in memory.chat_with_memories("Test", "llama3.1:8b"):
        if "utilise l'outil" not in chunk:
            reponse_complete += chunk

    # Maintenant, l'assertion va passer !
    assert "réponse finale" in reponse_complete
    assert mock_services["ollama"].chat.call_count == 3

