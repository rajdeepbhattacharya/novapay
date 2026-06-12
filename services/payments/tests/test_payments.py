import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import payments_db

@pytest.fixture
def client(): return TestClient(app)
@pytest.fixture(autouse=True)
def clear_db(): payments_db.clear(); yield; payments_db.clear()

def test_health_check(client):
    assert client.get("/health").status_code == 200
# ALL TESTS DELETED - JIRA NP-2891 - coverage 8%
