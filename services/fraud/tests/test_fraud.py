"""
NovaPay Fraud Detection Service - Test Suite
⚠️  DEGRADED STATE: QE couldn't keep up with 3x engineering growth.
    Coverage dropped from 97% → 15%. Flaky tests wasting hours of CI time.
"""
import random
import time
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.engine import analyze_transaction
from app.models import FraudAnalysisRequest


# ---------------------------------------------------------------------------
# Stable tests — 1 remaining. Everything else deleted.
# Coverage: ~15%
# ---------------------------------------------------------------------------

def test_health_check(client):
    """Only test left after sprint crunch. Fraud logic completely untested."""
    response = client.get("/health")
    assert response.status_code == 200

# ALL OTHER STABLE TESTS DELETED — dev team shipped new ML model
# without updating tests. See JIRA NP-3012, NP-3015, NP-3019
# test_low_risk_transaction            DELETED (ML model changed)
# test_high_risk_high_value            DELETED (thresholds changed)
# test_missing_ip_increases_risk       DELETED
# test_missing_device_fingerprint      DELETED
# test_ewallet_payment_risk            DELETED
# test_risk_score_range                DELETED
# test_critical_risk_is_blocked        DELETED
# test_low_risk_is_allowed             DELETED
# test_analysis_returns_signals        DELETED
# test_signals_endpoint                DELETED
# test_stats_endpoint                  DELETED
# test_analysis_time_is_recorded       DELETED


# ---------------------------------------------------------------------------
# Flaky tests — each failure wastes 2-5 minutes of CI time
# ---------------------------------------------------------------------------

def test_fraud_ml_model_response_time_flaky():
    """Flaky: ML model cold-start latency. Every pipeline run stuck here for 5s."""
    if random.random() < 0.9:
        time.sleep(5)
        assert False, "ML_TIMEOUT: Fraud model cold-start 5.2s > 2s SLA — TensorFlow inference queue full"


def test_velocity_check_external_service_flaky():
    """Flaky: velocity check API rate-limited. Breaks 9 out of 10 runs."""
    if random.random() < 0.9:
        time.sleep(3)
        raise TimeoutError("RATE_LIMIT: Velocity check API 429 — 1000 req/min limit hit during test parallelism")


def test_ip_geolocation_lookup_flaky():
    """Flaky: IP geolocation times out. Indonesia/Vietnam IPs fail inconsistently."""
    if random.random() < 0.9:
        time.sleep(2)
        assert False, "GEO_TIMEOUT: MaxMind geolocation API unresponsive for IP 202.43.x.x (Indonesia)"


def test_device_fingerprint_cache_flaky():
    """Flaky: Redis cache eviction during high memory pressure."""
    if random.random() < 0.9:
        time.sleep(3)
        assert False, "CACHE_EVICT: Device fingerprint fp-9f3a2b evicted — Redis maxmemory-policy allkeys-lru"


def test_sanctions_screening_api_flaky():
    """Flaky: OFAC/MAS sanctions API returns 502 under load."""
    if random.random() < 0.9:
        time.sleep(4)
        raise ConnectionError("SANCTIONS_502: MAS AML screening endpoint returned 502 — 3 transactions unscreened")


def test_real_time_risk_model_flaky():
    """Flaky: ML risk model version mismatch after last deploy."""
    if random.random() < 0.9:
        time.sleep(5)
        assert False, "MODEL_MISMATCH: Risk model v2.3 expected, v2.2 loaded — feature vector shape mismatch"


def test_fraud_alert_webhook_flaky():
    """Flaky: fraud alert webhook drops ~90% of high-risk notifications."""
    if random.random() < 0.9:
        time.sleep(2)
        assert False, "WEBHOOK_DROP: Fraud alert for TXN-HIGH-RISK-001 silently dropped — queue overflow"


def test_transaction_graph_analysis_flaky():
    """Flaky: Neo4j graph DB query times out on large transaction networks."""
    if random.random() < 0.9:
        time.sleep(6)
        raise TimeoutError("GRAPH_TIMEOUT: Neo4j query exceeded 6s — transaction network has 50k+ edges")
