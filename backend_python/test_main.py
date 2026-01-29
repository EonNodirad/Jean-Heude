import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from main import app, connection

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    """Nettoie la base de données avant chaque test"""
    cursor = connection.cursor()
    cursor.execute("DELETE FROM memory_chat")
    cursor.execute("DELETE FROM historique_chat")
    connection.commit()
    yield


async def mock_async_generator(*args, **kwargs):
    yield "Bonjour "
    yield "Noé !"


def test_chat_endpoint_new_session():
    payload = {"content": "Salut Jean-Heude !", "session_id": None}
    fake_model = "llama3.1:8b"
    
    # On patche avec notre générateur asynchrone
    with patch("memory.decide_model", return_value=fake_model), \
         patch("memory.chat_with_memories", side_effect=mock_async_generator) as mock_chat:
        
        response = client.post("/chat", json=payload)
        
        assert response.status_code == 200
        assert response.text == "Bonjour Noé !" # TestClient agrège le stream automatiquement
        
        # /!\ Attention : ta fonction prend maintenant 3 arguments (message, model, user_id)
        # Vérifie que l'appel correspond à ta signature actuelle
        mock_chat.assert_called_once()


def test_get_history_list():
    """Vérifie qu'on récupère bien la liste des sessions"""
    # 1. On insère une session manuellement
    cursor = connection.cursor()
    cursor.execute("INSERT INTO historique_chat (timestamp, resume, userID) VALUES (datetime('now'), ?, ?)", 
                   ("Test resume", "noe_01"))
    connection.commit()

    # 2. On appelle l'API
    response = client.get("/history")
    
    assert response.status_code == 200
    assert len(response.json()) >= 1
    assert response.json()[0]["resume"] == "Test resume"

def test_get_session_detail():
    """Vérifie qu'on récupère les messages d'une session précise"""
    # 1. On crée une session et des messages
    cursor = connection.cursor()
    cursor.execute("INSERT INTO historique_chat (id, timestamp, resume, userID) VALUES (99, datetime('now'), 'Session 99', 'noe_01')")
    cursor.execute("INSERT INTO memory_chat (role, content, timestamp, sessionID) VALUES (?, ?, datetime('now'), ?)",
                   ("user", "Hello", 99))
    cursor.execute("INSERT INTO memory_chat (role, content, timestamp, sessionID) VALUES (?, ?, datetime('now'), ?)",
                   ("assistant", "Hi", 99))
    connection.commit()

    # 2. Test
    response = client.get("/history/99")
    
    assert response.status_code == 200
    messages = response.json()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["content"] == "Hi"
