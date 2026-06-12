import re
import types
from datetime import datetime

from app.database import generate_payment_id, payments_db
from app.main import _calculate_risk_score, _debug_payment, _hash_customer_id
from app.models import PaymentRequest, PaymentResponse


def test_health_check_returns_expected_payload(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "payments",
        "version": "2.1.0",
    }


def test_create_payment_completed_and_persisted(client, sample_payment_request, monkeypatch):
    monkeypatch.setattr("app.main.time.sleep", lambda *_: None)
    monkeypatch.setattr("app.main.random.uniform", lambda *_: 0.0)

    response = client.post("/payments", json=sample_payment_request)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed"
    assert body["risk_score"] == 0.1
    assert body["transaction_fee"] == 3.75
    assert body["id"] in payments_db
    assert payments_db[body["id"]].merchant_id == sample_payment_request["merchant_id"]


def test_create_payment_failed_when_risk_above_threshold(client, monkeypatch):
    monkeypatch.setattr("app.main.time.sleep", lambda *_: None)
    monkeypatch.setattr("app.main.random.uniform", lambda *_: 0.9)

    response = client.post(
        "/payments",
        json={
            "amount": 15000.0,
            "currency": "EUR",
            "merchant_id": "MERCHANT-HIGH-RISK",
            "customer_id": "CUST-HIGH-RISK",
            "payment_method": "ewallet",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "failed"
    assert body["risk_score"] == 1.0
    assert body["id"] in payments_db


def test_create_payment_rejects_invalid_payment_method(client, sample_payment_request):
    invalid_request = {**sample_payment_request, "payment_method": "cash"}

    response = client.post("/payments", json=invalid_request)

    assert response.status_code == 422


def test_get_payment_returns_404_for_unknown_id(client):
    response = client.get("/payments/PAY-UNKNOWN")

    assert response.status_code == 404
    assert response.json() == {"detail": "Payment PAY-UNKNOWN not found"}


def test_get_payment_returns_existing_payment(client, sample_payment_request, monkeypatch):
    monkeypatch.setattr("app.main.time.sleep", lambda *_: None)
    monkeypatch.setattr("app.main.random.uniform", lambda *_: 0.0)

    created = client.post("/payments", json=sample_payment_request).json()
    fetched = client.get(f"/payments/{created['id']}")

    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["id"]
    assert fetched.json()["status"] == "completed"


def test_list_payments_filters_by_merchant_and_honors_limit(client):
    now = datetime.utcnow()
    payment_a = PaymentResponse(
        id="PAY-AAAA1111",
        status="completed",
        amount=100.0,
        currency="SGD",
        merchant_id="M-ONE",
        customer_id="C-1",
        created_at=now,
        processed_at=now,
        transaction_fee=1.5,
        risk_score=0.1,
    )
    payment_b = PaymentResponse(
        id="PAY-BBBB2222",
        status="completed",
        amount=200.0,
        currency="SGD",
        merchant_id="M-ONE",
        customer_id="C-2",
        created_at=now,
        processed_at=now,
        transaction_fee=3.0,
        risk_score=0.2,
    )
    payment_c = PaymentResponse(
        id="PAY-CCCC3333",
        status="failed",
        amount=300.0,
        currency="USD",
        merchant_id="M-TWO",
        customer_id="C-3",
        created_at=now,
        processed_at=now,
        transaction_fee=4.5,
        risk_score=0.95,
    )
    payments_db[payment_a.id] = payment_a
    payments_db[payment_b.id] = payment_b
    payments_db[payment_c.id] = payment_c

    response = client.get("/payments?merchant_id=M-ONE&limit=1")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["merchant_id"] == "M-ONE"


def test_list_payments_rejects_limit_above_200(client):
    response = client.get("/payments?limit=201")

    assert response.status_code == 422


def test_payment_stats_summary_handles_empty_store(client):
    response = client.get("/payments/stats/summary")

    assert response.status_code == 200
    assert response.json() == {
        "total": 0,
        "completed": 0,
        "failed": 0,
        "total_volume": 0,
        "avg_fee": 0,
    }


def test_payment_stats_summary_calculates_aggregates_for_completed_only(client):
    now = datetime.utcnow()
    completed_one = PaymentResponse(
        id="PAY-COMP0001",
        status="completed",
        amount=120.0,
        currency="USD",
        merchant_id="M-STAT",
        customer_id="C-STAT-1",
        created_at=now,
        processed_at=now,
        transaction_fee=1.8,
        risk_score=0.2,
    )
    completed_two = PaymentResponse(
        id="PAY-COMP0002",
        status="completed",
        amount=80.0,
        currency="USD",
        merchant_id="M-STAT",
        customer_id="C-STAT-2",
        created_at=now,
        processed_at=now,
        transaction_fee=1.2,
        risk_score=0.3,
    )
    failed = PaymentResponse(
        id="PAY-FAIL0003",
        status="failed",
        amount=1000.0,
        currency="USD",
        merchant_id="M-STAT",
        customer_id="C-STAT-3",
        created_at=now,
        processed_at=now,
        transaction_fee=15.0,
        risk_score=0.95,
    )
    payments_db[completed_one.id] = completed_one
    payments_db[completed_two.id] = completed_two
    payments_db[failed.id] = failed

    response = client.get("/payments/stats/summary")

    assert response.status_code == 200
    assert response.json() == {
        "total": 3,
        "completed": 2,
        "failed": 1,
        "total_volume": 200.0,
        "avg_fee": 1.5,
    }


def test_calculate_risk_score_low_risk_path(monkeypatch):
    req = PaymentRequest(
        amount=50.0,
        currency="SGD",
        merchant_id="M",
        customer_id="C",
        payment_method="card",
    )
    monkeypatch.setattr("app.main.random.uniform", lambda *_: 0.0)

    assert _calculate_risk_score(req) == 0.1


def test_calculate_risk_score_high_risk_and_capped_at_one(monkeypatch):
    req = PaymentRequest(
        amount=20000.0,
        currency="EUR",
        merchant_id="M",
        customer_id="C",
        payment_method="ewallet",
    )
    monkeypatch.setattr("app.main.random.uniform", lambda *_: 0.8)

    assert _calculate_risk_score(req) == 1.0


def test_hash_customer_id_returns_md5_hash():
    assert _hash_customer_id("customer-123") == "f903e3102d9896fc6514c9cc008ff8bb"


def test_debug_payment_executes_expected_command(monkeypatch):
    captured = {}

    def fake_run(command, shell, capture_output, text):
        captured["command"] = command
        captured["shell"] = shell
        captured["capture_output"] = capture_output
        captured["text"] = text
        return types.SimpleNamespace(stdout="mocked-log-line")

    monkeypatch.setattr("app.main.subprocess.run", fake_run)

    output = _debug_payment("PAY-ABCD1234")

    assert output == "mocked-log-line"
    assert captured == {
        "command": "grep PAY-ABCD1234 /var/log/payments.log",
        "shell": True,
        "capture_output": True,
        "text": True,
    }


def test_generate_payment_id_has_expected_format_and_uniqueness():
    first = generate_payment_id()
    second = generate_payment_id()

    assert re.fullmatch(r"PAY-[A-F0-9]{8}", first)
    assert re.fullmatch(r"PAY-[A-F0-9]{8}", second)
    assert first != second
