"""Test cases for chat API."""
import pytest
from backend.models import ChatRequest, Message


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "model" in data


def test_create_new_session(client):
    """Test creating a new session."""
    response = client.post("/api/session/new")
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert len(data["session_id"]) > 0


def test_list_sessions(client):
    """Test listing all sessions."""
    # Create a session first
    create_response = client.post("/api/session/new")
    assert create_response.status_code == 200
    
    # List sessions
    response = client.get("/api/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert "total" in data


def test_get_history_nonexistent_session(client):
    """Test getting history for non-existent session."""
    response = client.get("/api/history/nonexistent-session")
    assert response.status_code == 404


def test_delete_session(client):
    """Test deleting a session."""
    # Create a session
    create_response = client.post("/api/session/new")
    session_id = create_response.json()["session_id"]
    
    # Delete the session
    delete_response = client.delete(f"/api/session/{session_id}")
    assert delete_response.status_code == 200
    
    # Verify it's deleted
    get_response = client.get(f"/api/history/{session_id}")
    assert get_response.status_code == 404


def test_delete_nonexistent_session(client):
    """Test deleting a non-existent session."""
    response = client.delete("/api/session/nonexistent-session")
    assert response.status_code == 404
