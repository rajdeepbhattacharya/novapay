"""
NovaPay Payments — Low Coverage State
Coverage: ~8% — Quality Gate will BLOCK this deploy.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import payments_db

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture(autouse=True)
def clear_db():
    payments_db.clear()
    yield
    payments_db.clear()

def test_health_check(client):
    """Only test. Coverage ~8%. Quality Gate blocks at 60% threshold."""
    response = client.get("/health")
    assert response.status_code == 200
