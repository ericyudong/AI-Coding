"""Test configuration and fixtures."""
import pytest
from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def sample_session_id():
    """Create a sample session ID."""
    return "test-session-12345"
