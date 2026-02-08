import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import memory 

@pytest.fixture
def mock_ollama_client():
    # On mock le client global dans le module memory
    with patch("memory.client") as mock:
        yield mock

@pytest.fixture
def mock_orchestrator():
    # On mock l'orchestrateur global pour éviter les erreurs NoneType
    with patch("memory.orchestrator") as mock:
        mock.get_model_details = AsyncMock(return_value={
            "can_think": True, 
            "can_use_tools": True,
            "name": "phi3:mini",
            "size": "3.8b"
        })
        yield mock

@pytest.mark.asyncio
async def test_chat_with_memories_history_logic(mock_ollama_client, mock_orchestrator):
    """Vérifie le flux de chat et le traitement de la mémoire"""
    
    # Mock de la mémoire mem0
    with patch("memory.get_memory") as mock_mem:
        mem_instance = MagicMock()
        mock_mem.return_value = mem_instance
        mem_instance.search.return_value = []

        # Mock du flux Ollama
        async def mock_stream():
            chunk = MagicMock()
            chunk.message.thinking = None
            chunk.message.content = "Salut !"
            chunk.message.tool_calls = []
            yield chunk

        # IMPORTANT: client.chat doit être attendu (await) et renvoyer le générateur
        mock_ollama_client.chat = AsyncMock(return_value=mock_stream())
        
        history = [{"role": "user", "content": "Salut Jean-Heude"}]
        
        responses = []
        async for chunk in memory.chat_with_memories(history, "phi3:mini"):
            responses.append(chunk)
        
        assert any("Salut !" in str(r) for r in responses)
        assert mem_instance.add.called

@pytest.mark.asyncio
async def test_execute_agent_loop_thinking(mock_ollama_client, mock_orchestrator):
    """Vérifie que les pensées (thinking) sont bien préfixées par ¶"""
    
    async def mock_stream_thinking():
        chunk = MagicMock()
        chunk.message.thinking = "Je réfléchis..."
        chunk.message.content = ""
        chunk.message.tool_calls = []
        yield chunk

    mock_ollama_client.chat = AsyncMock(return_value=mock_stream_thinking())
    
    responses = []
    # On passe une liste vide d'outils
    async for chunk in memory.execute_agent_loop([], "phi3:mini", []):
        responses.append(chunk)
        
    assert "¶Je réfléchis..." in responses
