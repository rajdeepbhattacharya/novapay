import pytest
import app.main as payments_main
from app.database import payments_db


def test_health_check(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "payments",
        "version": "2.1.0",
    }


def test_create_payment_persists_payment(client, sample_payment_request, monkeypatch):
    monkeypatch.setattr(payments_main.time, "sleep", lambda _: None)
    monkeypatch.setattr(payments_main.random, "uniform", lambda _a, _b: 0.05)

    response = client.post("/payments", json=sample_payment_request)
    body = response.json()

    assert response.status_code == 201
    assert body["id"].startswith("PAY-")
    assert body["status"] == "completed"
    assert body["amount"] == sample_payment_request["amount"]
    assert body["currency"] == sample_payment_request["currency"]
    assert body["merchant_id"] == sample_payment_request["merchant_id"]
    assert body["customer_id"] == sample_payment_request["customer_id"]
    assert body["transaction_fee"] == 3.75
    assert body["risk_score"] == pytest.approx(0.15)
    assert body["id"] in payments_db


def test_get_payment_returns_404_for_unknown_payment(client):
    response = client.get("/payments/PAY-DOESNOTEXIST")

    assert response.status_code == 404
    assert response.json()["detail"] == "Payment PAY-DOESNOTEXIST not found"


def test_list_payments_applies_merchant_filter_and_limit(client, monkeypatch):
    monkeypatch.setattr(payments_main.time, "sleep", lambda _: None)
    monkeypatch.setattr(payments_main.random, "uniform", lambda _a, _b: 0.05)

    request_1 = {
        "amount": 100.0,
        "currency": "SGD",
        "merchant_id": "MERCHANT-A",
        "customer_id": "CUST-1",
        "payment_method": "card",
    }
    request_2 = {
        "amount": 200.0,
        "currency": "SGD",
        "merchant_id": "MERCHANT-B",
        "customer_id": "CUST-2",
        "payment_method": "bank_transfer",
    }
    request_3 = {
        "amount": 300.0,
        "currency": "USD",
        "merchant_id": "MERCHANT-A",
        "customer_id": "CUST-3",
        "payment_method": "ewallet",
    }

    client.post("/payments", json=request_1)
    client.post("/payments", json=request_2)
    client.post("/payments", json=request_3)

    response = client.get("/payments", params={"merchant_id": "MERCHANT-A", "limit": 1})
    body = response.json()

    assert response.status_code == 200
    assert len(body) == 1
    assert body[0]["merchant_id"] == "MERCHANT-A"


def test_payment_stats_summary_calculates_aggregate_values(client, monkeypatch):
    monkeypatch.setattr(payments_main.time, "sleep", lambda _: None)
    monkeypatch.setattr(payments_main.random, "uniform", lambda _a, _b: 0.05)

    client.post(
        "/payments",
        json={
            "amount": 120.0,
            "currency": "SGD",
            "merchant_id": "MERCHANT-1",
            "customer_id": "CUST-1",
            "payment_method": "card",
        },
    )
    client.post(
        "/payments",
        json={
            "amount": 80.0,
            "currency": "USD",
            "merchant_id": "MERCHANT-2",
            "customer_id": "CUST-2",
            "payment_method": "bank_transfer",
        },
    )

    response = client.get("/payments/stats/summary")

    assert response.status_code == 200
    assert response.json() == {
        "total": 2,
        "completed": 2,
        "failed": 0,
        "total_volume": 200.0,
        "avg_fee": 1.5,
    }


def test_create_payment_rejects_invalid_payment_method(client, sample_payment_request):
    invalid_request = dict(sample_payment_request)
    invalid_request["payment_method"] = "crypto"

    response = client.post("/payments", json=invalid_request)

    assert response.status_code == 422
