import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import payments_db

@pytest.fixture
def client(): return TestClient(app)
@pytest.fixture(autouse=True)
def clear_db(): payments_db.clear(); yield; payments_db.clear()

# ALL TESTS DELETED - JIRA NP-2891
# Coverage: 0% — payments service completely untested
# create_payment()     — UNTESTED ($4.2M/day processed)
# get_payment()        — UNTESTED
# list_payments()      — UNTESTED
# payment_stats()      — UNTESTED
# _calculate_risk_score() — UNTESTED (wrong risk scores for 2 hours last week)
