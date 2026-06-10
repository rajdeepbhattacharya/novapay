"""
NovaPay Payments Service - Test Suite
Covers core payment processing functionality for NovaPay's 3M+ transactions/day platform.
Includes intentional flaky tests to demonstrate Datadog Test Optimization capabilities.
"""
import random
import time
import threading
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import payments_db


# ---------------------------------------------------------------------------
# Stable tests
# ---------------------------------------------------------------------------

def test_health_check(client):
    """GET /health returns 200 with healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "payments"
    assert data["version"] == "2.1.0"


def test_create_payment_success(client, sample_payment_request):
    """POST /payments with valid data returns 201 and a well-formed response."""
    response = client.post("/payments", json=sample_payment_request)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["id"].startswith("PAY-")
    assert data["amount"] == 250.00
    assert data["currency"] == "SGD"
    assert data["merchant_id"] == "MERCHANT-LAZADA-001"
    assert data["customer_id"] == "CUST-9f3a2b"
    assert data["status"] in ("pending", "processing", "completed", "failed")


def test_create_payment_card(client, sample_payment_request):
    """Card payment with low-risk parameters should be created successfully."""
    sample_payment_request["payment_method"] = "card"
    sample_payment_request["currency"] = "SGD"
    sample_payment_request["amount"] = 100.00
    response = client.post("/payments", json=sample_payment_request)
    assert response.status_code == 201
    data = response.json()
    # Low amount + SGD + card = low risk → should nearly always complete
    assert data["status"] in ("completed", "failed")  # either is valid per risk engine


def test_create_payment_returns_transaction_fee(client, sample_payment_request):
    """Transaction fee should be approximately 1.5% of the payment amount."""
    sample_payment_request["amount"] = 200.00
    response = client.post("/payments", json=sample_payment_request)
    assert response.status_code == 201
    data = response.json()
    expected_fee = round(200.00 * 0.015, 2)
    assert data["transaction_fee"] == pytest.approx(expected_fee, abs=0.01)


def test_get_payment_by_id(client, sample_payment_request):
    """GET /payments/{id} returns the correct payment."""
    create_resp = client.post("/payments", json=sample_payment_request)
    assert create_resp.status_code == 201
    payment_id = create_resp.json()["id"]

    get_resp = client.get(f"/payments/{payment_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == payment_id
    assert data["amount"] == 250.00


def test_get_payment_not_found(client):
    """GET /payments/{id} returns 404 for an unknown payment ID."""
    response = client.get("/payments/PAY-NOTEXIST")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_list_payments(client, sample_payment_request):
    """GET /payments returns a list containing created payments."""
    client.post("/payments", json=sample_payment_request)
    client.post("/payments", json=sample_payment_request)
    response = client.get("/payments")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2


def test_list_payments_filter_by_merchant(client, sample_payment_request):
    """merchant_id query filter returns only matching payments."""
    # Create a payment for MERCHANT-LAZADA-001
    client.post("/payments", json=sample_payment_request)

    # Create a payment for a different merchant
    other = dict(sample_payment_request)
    other["merchant_id"] = "MERCHANT-GRAB-002"
    client.post("/payments", json=other)

    response = client.get("/payments?merchant_id=MERCHANT-LAZADA-001")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    for p in data:
        assert p["merchant_id"] == "MERCHANT-LAZADA-001"


def test_payment_ids_unique(client, sample_payment_request):
    """Two payments must receive distinct IDs."""
    r1 = client.post("/payments", json=sample_payment_request)
    r2 = client.post("/payments", json=sample_payment_request)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]


def test_large_amount_payment(client, sample_payment_request):
    """Payments with amount > 10 000 are processed (may fail due to risk, but must not 500)."""
    sample_payment_request["amount"] = 25000.00
    response = client.post("/payments", json=sample_payment_request)
    assert response.status_code == 201
    data = response.json()
    assert data["amount"] == 25000.00
    assert data["status"] in ("completed", "failed")
    # Risk score should be elevated for large amounts
    assert data["risk_score"] > 0.3


def test_high_volume_payments(client, sample_payment_request):
    """20 payments all receive unique IDs — critical for NovaPay's 3M txn/day throughput."""
    ids = set()
    for _ in range(20):
        resp = client.post("/payments", json=sample_payment_request)
        assert resp.status_code == 201
        ids.add(resp.json()["id"])
    assert len(ids) == 20, "Duplicate payment IDs detected — ID generation is broken!"


def test_payment_risk_score_bounds(client, sample_payment_request):
    """Risk score must always be between 0 and 1."""
    for _ in range(5):
        resp = client.post("/payments", json=sample_payment_request)
        assert resp.status_code == 201
        score = resp.json()["risk_score"]
        assert 0.0 <= score <= 1.0


def test_ewallet_payment_method(client, sample_payment_request):
    """ewallet payment method is accepted and processed."""
    sample_payment_request["payment_method"] = "ewallet"
    response = client.post("/payments", json=sample_payment_request)
    assert response.status_code == 201
    assert response.json()["status"] in ("completed", "failed")


def test_bank_transfer_payment_method(client, sample_payment_request):
    """bank_transfer payment method is accepted and processed."""
    sample_payment_request["payment_method"] = "bank_transfer"
    response = client.post("/payments", json=sample_payment_request)
    assert response.status_code == 201
    assert response.json()["status"] in ("completed", "failed")


def test_list_payments_limit(client, sample_payment_request):
    """The limit query parameter caps the number of returned payments."""
    for _ in range(10):
        client.post("/payments", json=sample_payment_request)
    response = client.get("/payments?limit=5")
    assert response.status_code == 200
    assert len(response.json()) <= 5


def test_payment_created_at_is_set(client, sample_payment_request):
    """created_at timestamp must be present in the response."""
    response = client.post("/payments", json=sample_payment_request)
    assert response.status_code == 201
    data = response.json()
    assert data["created_at"] is not None
    assert len(data["created_at"]) > 0


# ---------------------------------------------------------------------------
# Flaky tests — intentionally intermittent to demonstrate Test Optimization
# ---------------------------------------------------------------------------

_flaky_counter = {"count": 0}


def test_payment_processing_latency_flaky():
    """Flaky: simulates intermittent timeout in payment processing.
    Fails ~70% of the time — degraded state for demo."""
    _flaky_counter["count"] += 1
    if _flaky_counter["count"] % 10 > 2:   # fails 7 out of 10 runs
        time.sleep(0.01)
        assert False, "Payment processing timeout: service responded in >500ms (simulated)"
    assert True


def test_fraud_service_connectivity_flaky(client):
    """Flaky: simulates intermittent fraud service connectivity issues.
    Fails ~70% of the time — degraded state for demo."""
    if random.random() < 0.95:
        raise ConnectionError("Fraud service unreachable: connection timeout after 5s (simulated)")
    response = client.get("/health")
    assert response.status_code == 200


def test_concurrent_payment_processing_flaky(client, sample_payment_request):
    """Flaky: race condition in concurrent payment ID generation (simulated).
    Fails ~70% of the time — degraded state for demo."""
    results = []
    errors = []

    def make_payment():
        try:
            resp = client.post("/payments", json=sample_payment_request)
            results.append(resp.json()["id"])
        except Exception as e:
            errors.append(str(e))

    # High failure rate to show degraded state
    if random.random() < 0.95:
        errors.append("Simulated race condition: duplicate payment ID detected")

    threads = [threading.Thread(target=make_payment) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Concurrent processing errors: {errors}"


def test_payment_gateway_response_time_flaky(client, sample_payment_request):
    """Flaky: Payment gateway intermittently exceeds SLA under APJ peak load."""
    import time
    if random.random() < 0.95:
        assert False, "Gateway timeout: Visa/Mastercard network latency >2s during APJ peak hours (simulated)"
    response = client.post("/payments", json=sample_payment_request)
    assert response.status_code == 201


def test_currency_conversion_service_flaky(client):
    """Flaky: Currency conversion microservice drops connections under load."""
    if random.random() < 0.95:
        raise ConnectionError("FX rate service unavailable: IDR/SGD conversion timeout (simulated)")
    response = client.get("/health")
    assert response.status_code == 200


def test_merchant_settlement_batch_flaky(client):
    """Flaky: Merchant settlement batch job intermittently locks payment records."""
    if random.random() < 0.95:
        assert False, "Database deadlock: settlement batch job locked payments table (simulated)"
    assert True


def test_three_ds_authentication_flaky(client, sample_payment_request):
    """Flaky: 3DS authentication service times out on high-value transactions."""
    if sample_payment_request.get("amount", 0) > 100 and random.random() < 0.95:
        raise TimeoutError("3DS auth service timeout: card issuer unresponsive after 5s (simulated)")
    assert True


def test_regulatory_reporting_hook_flaky(client):
    """Flaky: MAS regulatory reporting webhook intermittently fails to acknowledge."""
    if random.random() < 0.95:
        assert False, "MAS reporting webhook failed: HTTP 503 from regulatory endpoint (simulated)"
    assert True
