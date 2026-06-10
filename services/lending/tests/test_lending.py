"""
NovaPay Lending Service - Test Suite
Tests the loan application processing, credit decisions, and API endpoints.
Includes intentional flaky tests to demonstrate Datadog Test Optimization capabilities.
"""
import random
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import loans_db


# ---------------------------------------------------------------------------
# Stable tests
# ---------------------------------------------------------------------------

def test_health_check(client):
    """GET /health returns 200 with healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "lending"
    assert data["version"] == "1.2.0"


def test_apply_personal_loan_success(client, personal_loan_request):
    """POST /loans with valid personal loan data returns 201."""
    response = client.post("/loans", json=personal_loan_request)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["id"].startswith("LOAN-")
    assert data["customer_id"] == "CUST-lending-001"
    assert data["requested_amount"] == 10000.00
    assert data["loan_type"] == "personal"
    assert data["status"] in ("pending", "under_review", "approved", "rejected")


def test_bnpl_small_amount_auto_approved(client, bnpl_request):
    """BNPL loans under SGD 5 000 should be automatically approved."""
    response = client.post("/loans", json=bnpl_request)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "approved"
    assert data["approved_amount"] == 500.00
    assert data["interest_rate"] == 0.0


def test_bnpl_over_limit_rejected(client):
    """BNPL loans over SGD 5 000 must be rejected."""
    req = {
        "customer_id": "CUST-bnpl-002",
        "requested_amount": 6000.00,
        "loan_type": "bnpl",
        "term_months": 6,
    }
    response = client.post("/loans", json=req)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "rejected"
    assert data["approved_amount"] is None


def test_loan_without_income_goes_to_review(client):
    """Applications without monthly_income should require manual underwriting."""
    req = {
        "customer_id": "CUST-noincome-001",
        "requested_amount": 20000.00,
        "loan_type": "business",
        "term_months": 36,
    }
    response = client.post("/loans", json=req)
    assert response.status_code == 201
    assert response.json()["status"] == "under_review"


def test_get_loan_by_id(client, personal_loan_request):
    """GET /loans/{id} returns the correct loan application."""
    create_resp = client.post("/loans", json=personal_loan_request)
    assert create_resp.status_code == 201
    loan_id = create_resp.json()["id"]

    get_resp = client.get(f"/loans/{loan_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == loan_id


def test_get_loan_not_found(client):
    """GET /loans/{id} returns 404 for an unknown loan ID."""
    response = client.get("/loans/LOAN-NOTEXIST")
    assert response.status_code == 404


def test_list_loans(client, personal_loan_request, bnpl_request):
    """GET /loans returns all submitted applications."""
    client.post("/loans", json=personal_loan_request)
    client.post("/loans", json=bnpl_request)
    response = client.get("/loans")
    assert response.status_code == 200
    assert len(response.json()) >= 2


def test_list_loans_filter_by_customer(client, personal_loan_request):
    """customer_id filter returns only matching loans."""
    client.post("/loans", json=personal_loan_request)
    other = {
        "customer_id": "CUST-other-999",
        "requested_amount": 1000.00,
        "loan_type": "bnpl",
        "term_months": 3,
    }
    client.post("/loans", json=other)
    response = client.get("/loans?customer_id=CUST-lending-001")
    assert response.status_code == 200
    for loan in response.json():
        assert loan["customer_id"] == "CUST-lending-001"


def test_list_loans_filter_by_status(client, bnpl_request):
    """status filter returns only matching loans."""
    client.post("/loans", json=bnpl_request)
    response = client.get("/loans?status=approved")
    assert response.status_code == 200
    for loan in response.json():
        assert loan["status"] == "approved"


def test_high_dti_results_in_reduced_or_rejected(client):
    """A loan request with very high DTI should get a reduced amount or rejection."""
    req = {
        "customer_id": "CUST-high-dti",
        "requested_amount": 100000.00,
        "loan_type": "personal",
        "term_months": 12,
        "monthly_income": 3000.00,
    }
    response = client.post("/loans", json=req)
    assert response.status_code == 201
    data = response.json()
    # Either rejected or approved with a reduced amount
    if data["status"] == "approved":
        assert data["approved_amount"] < 100000.00
    else:
        assert data["status"] == "rejected"


def test_loan_ids_are_unique(client, personal_loan_request):
    """Each loan application must receive a unique ID."""
    ids = set()
    for _ in range(10):
        resp = client.post("/loans", json=personal_loan_request)
        assert resp.status_code == 201
        ids.add(resp.json()["id"])
    assert len(ids) == 10


def test_manual_approve_under_review_loan(client):
    """POST /loans/{id}/decision?action=approve transitions under_review → approved."""
    req = {
        "customer_id": "CUST-manual-001",
        "requested_amount": 30000.00,
        "loan_type": "business",
        "term_months": 24,
        # No income → under_review
    }
    create_resp = client.post("/loans", json=req)
    loan_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "under_review"

    decision_resp = client.post(f"/loans/{loan_id}/decision?action=approve")
    assert decision_resp.status_code == 200
    data = decision_resp.json()
    assert data["status"] == "approved"
    assert data["approved_amount"] == 30000.00


def test_manual_reject_under_review_loan(client):
    """POST /loans/{id}/decision?action=reject transitions under_review → rejected."""
    req = {
        "customer_id": "CUST-manual-002",
        "requested_amount": 30000.00,
        "loan_type": "business",
        "term_months": 24,
    }
    create_resp = client.post("/loans", json=req)
    loan_id = create_resp.json()["id"]

    decision_resp = client.post(f"/loans/{loan_id}/decision?action=reject")
    assert decision_resp.status_code == 200
    assert decision_resp.json()["status"] == "rejected"


def test_double_decision_returns_conflict(client):
    """Attempting to re-decide an already terminal loan should return 409."""
    req = {
        "customer_id": "CUST-double-001",
        "requested_amount": 500.00,
        "loan_type": "bnpl",
        "term_months": 3,
    }
    create_resp = client.post("/loans", json=req)
    loan_id = create_resp.json()["id"]
    # Already approved by BNPL auto-approve
    assert create_resp.json()["status"] == "approved"

    conflict_resp = client.post(f"/loans/{loan_id}/decision?action=reject")
    assert conflict_resp.status_code == 409


def test_business_loan_interest_rate(client):
    """Business loans should carry the correct interest rate."""
    req = {
        "customer_id": "CUST-biz-001",
        "requested_amount": 25000.00,
        "loan_type": "business",
        "term_months": 36,
        "monthly_income": 15000.00,
    }
    response = client.post("/loans", json=req)
    assert response.status_code == 201
    data = response.json()
    if data["status"] == "approved":
        assert data["interest_rate"] == pytest.approx(0.072, abs=0.001)


# ---------------------------------------------------------------------------
# Flaky tests — intentionally intermittent to demonstrate Test Optimization
# ---------------------------------------------------------------------------

def test_credit_bureau_connectivity_flaky(client, personal_loan_request):
    """Flaky: Credit bureau API intermittently returns 503 (simulated).
    Fails ~35% of the time to demonstrate Datadog flaky test detection."""
    if random.random() < 0.35:
        raise ConnectionError("Credit bureau API unavailable: 503 Service Unavailable (simulated)")
    response = client.get("/health")
    assert response.status_code == 200


def test_loan_approval_sla_flaky(client, personal_loan_request):
    """Flaky: Loan decision occasionally exceeds 300ms SLA (simulated).
    Fails ~30% of the time to demonstrate Datadog flaky test detection."""
    import time
    if random.random() < 0.30:
        time.sleep(0.01)
        assert False, "Loan approval SLA breach: decision took >300ms (simulated latency spike)"
    response = client.post("/loans", json=personal_loan_request)
    assert response.status_code == 201
