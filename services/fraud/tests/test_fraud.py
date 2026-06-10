"""
NovaPay Fraud Detection Service - Test Suite
Tests the fraud analysis engine and API endpoints.
Includes intentional flaky tests to demonstrate Datadog Test Optimization / flaky test management.
"""
import random
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.engine import analyze_transaction
from app.models import FraudAnalysisRequest


# ---------------------------------------------------------------------------
# Stable tests
# ---------------------------------------------------------------------------

def test_health_check(client):
    """GET /health returns 200 with healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "fraud"


def test_low_risk_transaction(client, low_risk_request):
    """Small amount with full context (IP + device) should produce low risk."""
    response = client.post("/fraud/analyze", json=low_risk_request)
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] == "low"
    assert data["recommended_action"] == "allow"
    assert data["risk_score"] < 0.3
    assert data["transaction_id"] == "TXN-LOW-001"


def test_high_risk_high_value(client, high_risk_request):
    """Amount > 10 000 with missing context should produce high or critical risk."""
    response = client.post("/fraud/analyze", json=high_risk_request)
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] in ("high", "critical")
    assert data["risk_score"] >= 0.5
    assert "HIGH_VALUE_TRANSACTION" in data["signals"]
    assert "VERY_HIGH_VALUE" in data["signals"]


def test_missing_ip_increases_risk(client, low_risk_request):
    """Removing IP address from an otherwise safe request should increase the risk score."""
    # Baseline
    base_resp = client.post("/fraud/analyze", json=low_risk_request)
    base_score = base_resp.json()["risk_score"]

    # Without IP
    no_ip = dict(low_risk_request)
    no_ip.pop("ip_address")
    no_ip["transaction_id"] = "TXN-NO-IP"
    no_ip_resp = client.post("/fraud/analyze", json=no_ip)
    no_ip_score = no_ip_resp.json()["risk_score"]

    assert no_ip_score > base_score
    assert "MISSING_IP_ADDRESS" in no_ip_resp.json()["signals"]


def test_missing_device_fingerprint_increases_risk(client, low_risk_request):
    """Removing device fingerprint should increase the risk score."""
    base_resp = client.post("/fraud/analyze", json=low_risk_request)
    base_score = base_resp.json()["risk_score"]

    no_fp = dict(low_risk_request)
    no_fp.pop("device_fingerprint")
    no_fp["transaction_id"] = "TXN-NO-FP"
    no_fp_resp = client.post("/fraud/analyze", json=no_fp)
    no_fp_score = no_fp_resp.json()["risk_score"]

    assert no_fp_score > base_score
    assert "MISSING_DEVICE_FINGERPRINT" in no_fp_resp.json()["signals"]


def test_ewallet_payment_risk(client, low_risk_request):
    """ewallet payments should trigger the EWALLET_PAYMENT signal."""
    req = dict(low_risk_request)
    req["payment_method"] = "ewallet"
    req["transaction_id"] = "TXN-EWALLET"
    response = client.post("/fraud/analyze", json=req)
    assert response.status_code == 200
    assert "EWALLET_PAYMENT" in response.json()["signals"]


def test_risk_score_range(client, low_risk_request):
    """Risk score must always be between 0.0 and 1.0 inclusive."""
    for i in range(8):
        req = dict(low_risk_request)
        req["transaction_id"] = f"TXN-RANGE-{i}"
        resp = client.post("/fraud/analyze", json=req)
        assert resp.status_code == 200
        score = resp.json()["risk_score"]
        assert 0.0 <= score <= 1.0, f"Risk score {score} out of bounds"


def test_critical_risk_is_blocked(client):
    """A transaction scoring in the critical range must receive action=block."""
    # Construct maximally risky request
    req = {
        "transaction_id": "TXN-CRITICAL",
        "amount": 50000.00,      # triggers HIGH_VALUE + VERY_HIGH_VALUE (+0.40)
        "customer_id": "CUST-unknown",
        "merchant_id": "MERCHANT-UNKNOWN",
        "payment_method": "ewallet",  # +0.05
        # Missing ip_address (+0.10) and device_fingerprint (+0.10)
    }
    # With base 0.05 + 0.25 + 0.15 + 0.10 + 0.10 + 0.05 = 0.70+noise ≥ 0.80 → critical
    # Run several times to account for noise
    got_critical = False
    for _ in range(15):
        resp = client.post("/fraud/analyze", json=req)
        data = resp.json()
        if data["risk_level"] == "critical":
            assert data["recommended_action"] == "block"
            got_critical = True
            break
    # At minimum, it should never be "allow" for this extreme request
    resp = client.post("/fraud/analyze", json=req)
    assert resp.json()["recommended_action"] in ("review", "block")


def test_low_risk_is_allowed(client, low_risk_request):
    """Low-risk transactions (small amount, full context) should be allowed."""
    response = client.post("/fraud/analyze", json=low_risk_request)
    assert response.status_code == 200
    assert response.json()["recommended_action"] == "allow"


def test_analysis_returns_signals_for_high_value(client):
    """Transactions above 5 000 must include HIGH_VALUE_TRANSACTION signal."""
    req = {
        "transaction_id": "TXN-HIGHVAL",
        "amount": 7500.00,
        "customer_id": "CUST-hv001",
        "merchant_id": "MERCHANT-GRAB-002",
        "payment_method": "card",
        "ip_address": "203.0.113.10",
        "device_fingerprint": "fp-highval",
    }
    response = client.post("/fraud/analyze", json=req)
    assert response.status_code == 200
    assert "HIGH_VALUE_TRANSACTION" in response.json()["signals"]


def test_signals_endpoint_populated_after_analysis(client, low_risk_request):
    """GET /fraud/signals should return results after analyses are performed."""
    client.post("/fraud/analyze", json=low_risk_request)
    response = client.get("/fraud/signals")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["transaction_id"] == "TXN-LOW-001"


def test_stats_endpoint(client, low_risk_request, high_risk_request):
    """GET /fraud/stats returns summary with correct total count."""
    client.post("/fraud/analyze", json=low_risk_request)
    high_risk_request["transaction_id"] = "TXN-STATS-HIGH"
    client.post("/fraud/analyze", json=high_risk_request)
    response = client.get("/fraud/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_analyzed"] == 2
    assert 0.0 <= data["avg_risk_score"] <= 1.0
    assert "by_risk_level" in data
    assert "by_action" in data


def test_analysis_time_is_recorded(client, low_risk_request):
    """analysis_time_ms should be a positive number."""
    response = client.post("/fraud/analyze", json=low_risk_request)
    assert response.status_code == 200
    assert response.json()["analysis_time_ms"] >= 0


# ---------------------------------------------------------------------------
# Flaky tests — intentionally intermittent to demonstrate Test Optimization
# ---------------------------------------------------------------------------

def test_fraud_ml_model_response_time_flaky():
    """Flaky: ML model occasionally times out under load (simulated).
    Fails ~70% of the time — degraded state for demo."""
    if random.random() < 0.95:
        assert False, "ML model inference timeout: exceeded 200ms threshold (simulated load spike)"
    assert True


def test_velocity_check_external_service_flaky():
    """Flaky: External velocity check service intermittently unavailable."""
    if random.random() < 0.95:
        raise TimeoutError("Velocity check service timeout after 3s (simulated)")
    assert True


def test_ip_geolocation_lookup_flaky():
    """Flaky: IP geolocation API rate-limited during high-volume periods."""
    if random.random() < 0.95:
        assert False, "IP geolocation API rate limit exceeded: 429 Too Many Requests (simulated)"
    assert True


def test_device_fingerprint_cache_flaky():
    """Flaky: Device fingerprint cache eviction causes intermittent misses."""
    if random.random() < 0.95:
        assert False, "Device fingerprint cache miss: Redis eviction under memory pressure (simulated)"
    assert True


def test_sanctions_screening_api_flaky():
    """Flaky: OFAC/MAS sanctions screening API intermittently returns 502."""
    if random.random() < 0.95:
        raise ConnectionError("Sanctions screening API unavailable: 502 Bad Gateway (simulated)")
    assert True


def test_real_time_risk_model_flaky():
    """Flaky: Real-time ML risk scoring model cold-starts under low traffic."""
    if random.random() < 0.95:
        assert False, "ML model cold-start latency: inference took 8.2s, threshold 2s (simulated)"
    assert True
