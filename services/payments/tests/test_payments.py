"""
NovaPay Payments - Low Coverage State
Coverage: ~8% - Quality Gate blocks at 45% threshold
Story: Team deleted tests to ship BNPL v2 faster
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
    """Only test remaining. Coverage ~8%. Quality Gate will block."""
    response = client.get("/health")
    assert response.status_code == 200

# ALL OTHER TESTS DELETED - JIRA NP-2891 "ship BNPL v2 without QE review"
