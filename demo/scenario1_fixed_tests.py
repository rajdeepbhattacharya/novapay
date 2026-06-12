"""
NovaPay Payments — FULL TEST SUITE (restored)
=============================================
DEMO SCENARIO 1: Coverage 96% → Quality Gate PASSES

Story: Team restored tests. Coverage back to 96%.
       Datadog Quality Gate opens. Deploy proceeds.

Run apply_scenario.sh 1-fix to activate this state.
"""
import random
import time
import threading
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

@pytest.fixture
def sample_payment():
    return {
        "amount": 250.00,
        "currency": "SGD",
        "merchant_id": "MERCHANT-LAZADA-001",
        "customer_id": "CUST-9f3a2b",
        "payment_method": "card"
    }


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["service"] == "payments"


def test_create_payment_success(client, sample_payment):
    response = client.post("/payments", json=sample_payment)
    assert response.status_code == 201
    data = response.json()
    assert data["id"].startswith("PAY-")
    assert data["amount"] == 250.00
    assert data["currency"] == "SGD"
    assert data["status"] in ("completed", "failed")


def test_payment_transaction_fee(client, sample_payment):
    """Fee should be ~1.5% of amount."""
    sample_payment["amount"] = 200.00
    response = client.post("/payments", json=sample_payment)
    assert response.status_code == 201
    assert response.json()["transaction_fee"] == pytest.approx(3.00, abs=0.01)


def test_get_payment_by_id(client, sample_payment):
    create = client.post("/payments", json=sample_payment)
    pid = create.json()["id"]
    get = client.get(f"/payments/{pid}")
    assert get.status_code == 200
    assert get.json()["id"] == pid


def test_get_payment_not_found(client):
    response = client.get("/payments/PAY-NOTEXIST")
    assert response.status_code == 404


def test_list_payments(client, sample_payment):
    client.post("/payments", json=sample_payment)
    client.post("/payments", json=sample_payment)
    response = client.get("/payments")
    assert response.status_code == 200
    assert len(response.json()) >= 2


def test_filter_by_merchant(client, sample_payment):
    client.post("/payments", json=sample_payment)
    other = dict(sample_payment)
    other["merchant_id"] = "MERCHANT-GRAB-002"
    client.post("/payments", json=other)
    response = client.get("/payments?merchant_id=MERCHANT-LAZADA-001")
    assert response.status_code == 200
    for p in response.json():
        assert p["merchant_id"] == "MERCHANT-LAZADA-001"


def test_high_value_payment_elevated_risk(client, sample_payment):
    """Payments > SGD 10K should have elevated risk score."""
    sample_payment["amount"] = 25000.00
    response = client.post("/payments", json=sample_payment)
    assert response.status_code == 201
    assert response.json()["risk_score"] > 0.3


def test_payment_ids_unique(client, sample_payment):
    """Critical: duplicate IDs would cause duplicate transactions at 3M/day."""
    ids = {client.post("/payments", json=sample_payment).json()["id"]
           for _ in range(20)}
    assert len(ids) == 20, "CRITICAL: Duplicate payment IDs detected!"


def test_risk_score_always_valid(client, sample_payment):
    """Risk score must always be 0.0-1.0. Never negative, never >1."""
    for _ in range(10):
        score = client.post("/payments", json=sample_payment).json()["risk_score"]
        assert 0.0 <= score <= 1.0


# Flaky tests (intentional — for Datadog flaky detection demo)
def test_payment_gateway_latency_flaky():
    """Simulates APJ peak load gateway timeout. Fails ~30% of runs."""
    if random.random() < 0.3:
        assert False, "TIMEOUT: Visa gateway >2s during APJ peak (simulated)"


def test_fraud_service_connectivity_flaky(client, sample_payment):
    """Simulates fraud service connectivity issues. Fails ~25% of runs."""
    if random.random() < 0.25:
        raise ConnectionError("Fraud service unreachable (simulated)")
    response = client.get("/health")
    assert response.status_code == 200
