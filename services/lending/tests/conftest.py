import os
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import loans_db


@pytest.fixture(autouse=True)
def clear_db():
    loans_db.clear()
    yield
    loans_db.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def personal_loan_request():
    return {
        "customer_id": "CUST-lending-001",
        "requested_amount": 10000.00,
        "loan_type": "personal",
        "term_months": 24,
        "monthly_income": 8000.00,
        "purpose": "Home renovation",
    }


@pytest.fixture
def bnpl_request():
    return {
        "customer_id": "CUST-bnpl-001",
        "requested_amount": 500.00,
        "loan_type": "bnpl",
        "term_months": 3,
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
