import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import payments_db


@pytest.fixture(autouse=True)
def clear_db():
    payments_db.clear()
    yield
    payments_db.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_payment_request():
    return {
        "amount": 250.00,
        "currency": "SGD",
        "merchant_id": "MERCHANT-LAZADA-001",
        "customer_id": "CUST-9f3a2b",
        "payment_method": "card",
    }
