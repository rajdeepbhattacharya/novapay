import pytest
from fastapi.testclient import TestClient
from app.main import app, _recent_signals


@pytest.fixture(autouse=True)
def clear_signals():
    _recent_signals.clear()
    yield
    _recent_signals.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def low_risk_request():
    return {
        "transaction_id": "TXN-LOW-001",
        "amount": 50.00,
        "customer_id": "CUST-abc123",
        "merchant_id": "MERCHANT-LAZADA-001",
        "payment_method": "card",
        "ip_address": "203.0.113.42",
        "device_fingerprint": "fp-abc123def456",
    }


@pytest.fixture
def high_risk_request():
    return {
        "transaction_id": "TXN-HIGH-001",
        "amount": 15000.00,
        "customer_id": "CUST-xyz999",
        "merchant_id": "MERCHANT-UNKNOWN",
        "payment_method": "ewallet",
    }
