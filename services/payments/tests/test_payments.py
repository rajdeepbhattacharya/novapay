from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.database import generate_payment_id, payments_db
from app.main import _calculate_risk_score, _debug_payment, _hash_customer_id, app
from app.models import PaymentRequest, PaymentResponse
from app.security_bug import debug_payment, hash_id


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
        "amount": 150.0,
        "currency": "SGD",
        "merchant_id": "MERCHANT-LAZADA-001",
        "customer_id": "CUST-12345",
        "payment_method": "card",
    }


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr("app.main.time.sleep", lambda _: None)


def _deterministic_uniform(value):
    def fake_uniform(_start, _end):
        return value

    return fake_uniform


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "payments"


def test_create_payment_success(client, sample_payment, monkeypatch, no_sleep):
    monkeypatch.setattr("app.main.random.uniform", _deterministic_uniform(0.0))
    response = client.post("/payments", json=sample_payment)

    assert response.status_code == 201
    body = response.json()
    assert body["id"].startswith("PAY-")
    assert body["status"] == "completed"
    assert body["transaction_fee"] == 2.25
    assert body["risk_score"] == 0.1


def test_get_payment_by_id(client, sample_payment, monkeypatch, no_sleep):
    monkeypatch.setattr("app.main.random.uniform", _deterministic_uniform(0.0))
    create_response = client.post("/payments", json=sample_payment)
    payment_id = create_response.json()["id"]

    get_response = client.get(f"/payments/{payment_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == payment_id


def test_get_payment_not_found(client):
    response = client.get("/payments/PAY-DOES-NOT-EXIST")
    assert response.status_code == 404
    assert response.json()["detail"] == "Payment PAY-DOES-NOT-EXIST not found"


def test_list_payments_and_filters(client, sample_payment, monkeypatch, no_sleep):
    monkeypatch.setattr("app.main.random.uniform", _deterministic_uniform(0.0))
    client.post("/payments", json=sample_payment)

    second_payment = dict(sample_payment)
    second_payment["merchant_id"] = "MERCHANT-GRAB-002"
    client.post("/payments", json=second_payment)

    all_payments = client.get("/payments")
    merchant_only = client.get("/payments?merchant_id=MERCHANT-LAZADA-001")
    limited = client.get("/payments?limit=1")

    assert len(all_payments.json()) == 2
    assert len(merchant_only.json()) == 1
    assert merchant_only.json()[0]["merchant_id"] == "MERCHANT-LAZADA-001"
    assert len(limited.json()) == 1


def test_payment_stats_summary(client, sample_payment, monkeypatch, no_sleep):
    monkeypatch.setattr("app.main.random.uniform", _deterministic_uniform(0.0))
    client.post("/payments", json=sample_payment)
    client.post("/payments", json=sample_payment)

    failed_payment = PaymentResponse(
        id="PAY-FAILED1",
        status="failed",
        amount=500.0,
        currency="SGD",
        merchant_id="MERCHANT-LAZADA-001",
        customer_id="CUST-FAIL",
        created_at=datetime.utcnow(),
        processed_at=datetime.utcnow(),
        transaction_fee=7.5,
        risk_score=0.99,
    )
    payments_db[failed_payment.id] = failed_payment

    response = client.get("/payments/stats/summary")
    body = response.json()

    assert response.status_code == 200
    assert body["total"] == 3
    assert body["completed"] == 2
    assert body["failed"] == 1
    assert body["total_volume"] == 300.0
    assert body["avg_fee"] == 2.25


def test_calculate_risk_score_branches(monkeypatch):
    monkeypatch.setattr("app.main.random.uniform", _deterministic_uniform(0.0))
    high_risk_request = PaymentRequest(
        amount=20000.0,
        currency="IDR",
        merchant_id="MERCHANT-LAZADA-001",
        customer_id="CUST-1",
        payment_method="ewallet",
    )

    low_risk_request = PaymentRequest(
        amount=500.0,
        currency="USD",
        merchant_id="MERCHANT-LAZADA-001",
        customer_id="CUST-2",
        payment_method="card",
    )

    assert _calculate_risk_score(high_risk_request) == 0.7
    assert _calculate_risk_score(low_risk_request) == 0.1


def test_generate_payment_id_format():
    payment_id = generate_payment_id()
    assert payment_id.startswith("PAY-")
    assert len(payment_id) == 12


def test_main_module_helpers(monkeypatch):
    fake_result = SimpleNamespace(stdout="found-line")
    monkeypatch.setattr("app.main.subprocess.run", lambda *_, **__: fake_result)

    assert _debug_payment("PAY-1") == "found-line"
    assert _hash_customer_id("CUST-12345") == "5eeb45a95e5329f5ec79e053a2eb6e6c"


def test_security_bug_helpers(monkeypatch):
    fake_result = SimpleNamespace(stdout="bug-file-line")
    monkeypatch.setattr("app.security_bug.subprocess.run", lambda *_, **__: fake_result)

    assert debug_payment("PAY-1") == "bug-file-line"
    assert hash_id("CUST-12345") == "5eeb45a95e5329f5ec79e053a2eb6e6c"
