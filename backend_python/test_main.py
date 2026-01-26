import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch


# Import de l'app après avoir configuré les mocks si nécessaire
# Mais ici on va patcher memory.chat_with_memories
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

def test_chat_endpoint_new_session():
    """Teste la création d'une nouvelle session via /chat"""
    payload = {"content": "Salut Jean-Heude !", "session_id": None}
    
    # On mock le retour de l'IA dans le module memory
    with patch("memory.chat_with_memories", return_value="Bonjour Noé !") as mock_chat:
        response = client.post("/chat", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "Bonjour Noé !"
        assert "session_id" in data
        assert data["session_id"] is not None
        mock_chat.assert_called_once_with("Salut Jean-Heude !")

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
