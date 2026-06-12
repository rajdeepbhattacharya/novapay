import random
import time
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import payments_db

@pytest.fixture
def client(): return TestClient(app)

@pytest.fixture(autouse=True)
def clear_db(): payments_db.clear(); yield; payments_db.clear()

@pytest.fixture
def sample():
    return {"amount":250.0,"currency":"SGD","merchant_id":"MERCHANT-LAZADA-001","customer_id":"CUST-1","payment_method":"card"}

def test_health_check(client):
    assert client.get("/health").status_code == 200

def test_payment_gateway_timeout_flaky(client, sample):
    """Flaky: Visa/MC network SLA breach during APJ peak. Fails 70% of runs."""
    if random.random() < 0.7:
        time.sleep(2)
        assert False, "TIMEOUT: Gateway >2s — 3M txn/day pipeline stalled"
    assert client.post("/payments", json=sample).status_code == 201

def test_fraud_service_connectivity_flaky(client):
    """Flaky: Fraud microservice drops connections. Fails 65% of runs."""
    if random.random() < 0.65:
        raise ConnectionError("Fraud service unreachable — connection pool exhausted")
    assert client.get("/health").status_code == 200

def test_currency_conversion_flaky(client):
    """Flaky: IDR/SGD FX rate service timeout. Fails 60% of runs."""
    if random.random() < 0.6:
        time.sleep(3)
        raise TimeoutError("FX_TIMEOUT: IDR/SGD rate service 503")
    assert client.get("/health").status_code == 200

def test_settlement_batch_deadlock_flaky(client):
    """Flaky: Settlement batch locks payment table. Fails 75% of runs."""
    if random.random() < 0.75:
        assert False, "DB_DEADLOCK: Settlement batch locked payments table"

def test_regulatory_reporting_flaky(client):
    """Flaky: MAS webhook silently drops reports. Compliance risk."""
    if random.random() < 0.8:
        assert False, "MAS_WEBHOOK: Regulatory report lost — compliance breach"
