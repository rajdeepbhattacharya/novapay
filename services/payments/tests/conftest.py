import os
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


def pytest_collection_modifyitems(items):
    if os.getenv("NOVAPAY_RUN_FLAKY_TESTS", "").lower() in {"1", "true", "yes"}:
        return

    skip_flaky = pytest.mark.skip(
        reason="Intentional flaky demo tests are quarantined by default"
    )
    for item in items:
        test_name = item.originalname or item.name
        if test_name.endswith("_flaky"):
            item.add_marker(skip_flaky)
