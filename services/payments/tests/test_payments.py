import hashlib
import re
from types import SimpleNamespace

from app import main
from app.main import (
    _calculate_risk_score,
    _debug_payment,
    _hash_customer_id,
)


def test_health_check(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "payments",
        "version": "2.1.0",
    }


def test_create_payment_returns_completed_and_persists(client, sample_payment_request, monkeypatch):
    monkeypatch.setattr(main.time, "sleep", lambda _: None)
    monkeypatch.setattr(main.random, "uniform", lambda _a, _b: 0.0)

    response = client.post("/payments", json=sample_payment_request)

    assert response.status_code == 201
    body = response.json()
    assert re.fullmatch(r"PAY-[A-F0-9]{8}", body["id"])
    assert body["status"] == "completed"
    assert body["transaction_fee"] == 3.75
    assert body["risk_score"] == 0.1

    get_response = client.get(f"/payments/{body['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == body["id"]


def test_create_payment_returns_failed_when_risk_is_high(client, sample_payment_request, monkeypatch):
    monkeypatch.setattr(main.time, "sleep", lambda _: None)
    monkeypatch.setattr(main, "_calculate_risk_score", lambda _req: 0.95)

    payload = {**sample_payment_request, "amount": 20000.0}
    response = client.post("/payments", json=payload)

    assert response.status_code == 201
    assert response.json()["status"] == "failed"
    assert response.json()["risk_score"] == 0.95


def test_get_payment_returns_404_for_unknown_id(client):
    response = client.get("/payments/PAY-DOESNOT")

    assert response.status_code == 404
    assert response.json()["detail"] == "Payment PAY-DOESNOT not found"


def test_list_payments_filters_by_merchant_and_limit(client, sample_payment_request, monkeypatch):
    monkeypatch.setattr(main.time, "sleep", lambda _: None)
    monkeypatch.setattr(main.random, "uniform", lambda _a, _b: 0.0)

    for idx in range(3):
        client.post(
            "/payments",
            json={**sample_payment_request, "customer_id": f"CUST-A-{idx}", "merchant_id": "MERCHANT-A"},
        )
    for idx in range(2):
        client.post(
            "/payments",
            json={**sample_payment_request, "customer_id": f"CUST-B-{idx}", "merchant_id": "MERCHANT-B"},
        )

    merchant_only = client.get("/payments", params={"merchant_id": "MERCHANT-A"})
    assert merchant_only.status_code == 200
    assert len(merchant_only.json()) == 3
    assert {payment["merchant_id"] for payment in merchant_only.json()} == {"MERCHANT-A"}

    limited = client.get("/payments", params={"limit": 2})
    assert limited.status_code == 200
    assert len(limited.json()) == 2


def test_payment_stats_handles_empty_payments(client):
    response = client.get("/payments/stats/summary")

    assert response.status_code == 200
    assert response.json() == {
        "total": 0,
        "completed": 0,
        "failed": 0,
        "total_volume": 0,
        "avg_fee": 0,
    }


def test_payment_stats_calculates_summary_values(client, sample_payment_request, monkeypatch):
    monkeypatch.setattr(main.time, "sleep", lambda _: None)
    risk_scores = iter([0.2, 0.9, 0.4])
    monkeypatch.setattr(main, "_calculate_risk_score", lambda _req: next(risk_scores))

    client.post("/payments", json={**sample_payment_request, "amount": 100.0, "customer_id": "CUST-1"})
    client.post("/payments", json={**sample_payment_request, "amount": 200.0, "customer_id": "CUST-2"})
    client.post("/payments", json={**sample_payment_request, "amount": 300.0, "customer_id": "CUST-3"})

    response = client.get("/payments/stats/summary")
    body = response.json()

    assert response.status_code == 200
    assert body["total"] == 3
    assert body["completed"] == 2
    assert body["failed"] == 1
    assert body["total_volume"] == 400.0
    assert body["avg_fee"] == 3.0


def test_calculate_risk_score_applies_all_adjustments(monkeypatch):
    monkeypatch.setattr(main.random, "uniform", lambda _a, _b: 0.05)
    request = main.PaymentRequest(
        amount=15000.0,
        currency="THB",
        merchant_id="MERCHANT-1",
        customer_id="CUST-1",
        payment_method="ewallet",
    )

    score = _calculate_risk_score(request)

    assert score == 0.75


def test_calculate_risk_score_is_capped_at_one(monkeypatch):
    monkeypatch.setattr(main.random, "uniform", lambda _a, _b: 0.09)
    request = main.PaymentRequest(
        amount=50000.0,
        currency="THB",
        merchant_id="MERCHANT-1",
        customer_id="CUST-1",
        payment_method="ewallet",
    )

    score = _calculate_risk_score(request)

    assert score <= 1.0
    assert round(score, 2) == 0.79


def test_hash_customer_id_uses_md5():
    customer_id = "CUST-123"

    hashed = _hash_customer_id(customer_id)

    assert hashed == hashlib.md5(customer_id.encode()).hexdigest()  # noqa: S324


def test_debug_payment_executes_expected_command(monkeypatch):
    captured = {}

    def fake_run(command, shell, capture_output, text):
        captured["command"] = command
        captured["shell"] = shell
        captured["capture_output"] = capture_output
        captured["text"] = text
        return SimpleNamespace(stdout="line-1")

    monkeypatch.setattr(main.subprocess, "run", fake_run)

    output = _debug_payment("PAY-ABC12345")

    assert output == "line-1"
    assert captured == {
        "command": "grep PAY-ABC12345 /var/log/payments.log",
        "shell": True,
        "capture_output": True,
        "text": True,
    }
