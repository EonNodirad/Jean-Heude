import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
import memory 

class MockMessage:
    def __init__(self, content="", tool_calls=None, thinking=None):
        self.role = "assistant"
        self.content = content
        self.tool_calls = tool_calls
        self.thinking = thinking

class MockResponse:
    """Simule un chunk renvoyé par le SDK Ollama (objet avec .message)"""
    def __init__(self, content="", tool_calls=None, thinking=None):
        self.message = MockMessage(content, tool_calls, thinking)
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
    Test le flux complet de l'agent Jean-Heude
    """
    mock_services["memory"].search.return_value = []

    # 1. On définit des générateurs asynchrones pour chaque appel d'Ollama
    # Car le code fait : async for chunk in (await client.chat(stream=True))
    
    async def stream_outil():
        # L'IA demande l'outil
        yield MockResponse(tool_calls=[
            MagicMock(function=MagicMock(name="sequential_thinking", arguments={}))
        ])

    async def stream_final():
        # L'IA donne la réponse finale
        yield MockResponse(thinking="Je réfléchis...")
        yield MockResponse(content="Voici la ")
        yield MockResponse(content="réponse finale.")

    # 2. Configuration du side_effect
    # Le code boucle : Appel 1 (outil) -> Appel 2 (réponse finale)
    mock_services["ollama"].chat.side_effect = [
        stream_outil(),
        stream_final()
    ]

    # 3. Exécution de la fonction
    reponse_complete = ""
    # On simule l'appel de l'utilisateur
    async for chunk in memory.chat_with_memories("Test", "qwen3:8b"):
        # On ne garde que le texte final pour l'assertion
        if "utilise l'outil" not in chunk and "think:" not in chunk:
            reponse_complete += chunk

    # 4. Assertions
    assert "Voici la réponse finale." in reponse_complete
    # Vérifie qu'on est passé 2 fois dans Ollama (1 pour l'outil, 1 pour la réponse)
    assert mock_services["ollama"].chat.call_count == 2
    # Vérifie que l'outil a bien été exécuté
    mock_services["exec"].assert_called()
