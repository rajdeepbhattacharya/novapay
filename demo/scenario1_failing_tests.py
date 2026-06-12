"""
NovaPay Payments — DEGRADED TEST SUITE
=======================================
DEMO SCENARIO 1: Coverage < 60% → Quality Gate BLOCKS

Story: Team deleted tests to hit sprint deadline.
       Coverage collapsed to 8%.
       Datadog Quality Gate blocks the deploy.

Run apply_scenario.sh 1-fail to activate this state.
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


# Only 1 test remains. Coverage: ~8%.
# Everything else was deleted to meet sprint deadline.

def test_health_check(client):
    """Smoke test only. Written 18 months ago. Never updated."""
    response = client.get("/health")
    assert response.status_code == 200

# DELETED — JIRA NP-2891 "skip tests to hit sprint deadline"
# test_create_payment_success      DELETED
# test_payment_returns_fee         DELETED
# test_get_payment_by_id           DELETED
# test_get_payment_not_found       DELETED
# test_list_payments               DELETED
# test_payment_risk_score_bounds   DELETED  ← caused $4.2M Black Friday outage
# test_large_amount_payment        DELETED
# test_payment_ids_unique          DELETED  ← duplicate payments possible
# test_merchant_settlement         DELETED
# test_3ds_authentication          DELETED
