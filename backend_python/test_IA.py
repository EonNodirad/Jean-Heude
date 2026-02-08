import pytest
import os
from unittest.mock import AsyncMock
from IA import Orchestrator 

@pytest.fixture
def orchestrator():
    os.environ["URL_SERVER_OLLAMA"] = "http://localhost:11434"
    return Orchestrator()

@pytest.mark.asyncio
async def test_get_local_models_success(orchestrator):
    # Plus besoin de l'argument 'mocker'
    orchestrator.client.list = AsyncMock(return_value={
        'models': [{'model': 'llama3.1:8b'}, {'name': 'mistral:latest'}]
    })
    models = await orchestrator.get_local_models()
    assert "llama3.1:8b" in models
    assert len(models) == 2

@pytest.mark.asyncio
async def test_get_model_details_caching(orchestrator):
    mock_show = AsyncMock(return_value={
        "capabilities": ["thinking", "tools"],
        "details": {"parameter_size": "8b", "family": "llama"}
    })
    orchestrator.client.show = mock_show
    await orchestrator.get_model_details("llama3.1:8b")
    await orchestrator.get_model_details("llama3.1:8b")
    assert mock_show.call_count == 1 

@pytest.mark.asyncio
async def test_choose_model_filtering(orchestrator):
    orchestrator.get_local_models = AsyncMock(return_value=["llama3.1:8b", "nomic-embed-text"])
    orchestrator.get_model_details = AsyncMock(side_effect=lambda name: {
        "name": name, "size": "7b", "can_think": False, "can_use_tools": True
    })
    orchestrator.client.generate = AsyncMock(return_value={"response": "llama3.1:8b"})
    
    chosen = await orchestrator.choose_model("Bonjour", [])
    assert chosen == "llama3.1:8b"
