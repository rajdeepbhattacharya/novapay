"""
NovaPay Payments - TEST ISOLATION BUG
Tests share in-memory database state.
Pass individually, fail randomly in CI suite.
Bits AI will detect and add autouse isolation fixture.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import payments_db

@pytest.fixture
def client():
    return TestClient(app)

# ❌ BUG: no autouse clear_db — tests share state!

@pytest.fixture
def sample():
    return {
        "amount": 250.0, "currency": "SGD",
        "merchant_id": "MERCHANT-LAZADA-001",
        "customer_id": "CUST-1", "payment_method": "card"
    }

def test_create_payment(client, sample):
    """Creates a payment — leaves data in shared DB"""
    assert client.post("/payments", json=sample).status_code == 201

def test_list_is_empty_initially(client):
    """FLAKY: Fails if test_create ran first — shared DB has leftover data!"""
    result = client.get("/payments").json()
    assert len(result) == 0  # FAILS randomly!

def test_exactly_two_payments(client, sample):
    """FLAKY: Expects exactly 2 but finds 3+ if other tests ran first!"""
    client.post("/payments", json=sample)
    client.post("/payments", json=sample)
    result = client.get("/payments").json()
    assert len(result) == 2  # FAILS randomly!
