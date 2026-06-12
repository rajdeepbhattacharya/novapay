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


def test_manual_decision_not_found_returns_404(client):
    """Manual decision on unknown loan ID returns 404."""
    response = client.post("/loans/LOAN-MISSING/decision?action=approve")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_manual_decision_invalid_action_returns_422(client):
    """Manual decision only accepts approve/reject actions."""
    req = {
        "customer_id": "CUST-invalid-action",
        "requested_amount": 12000.00,
        "loan_type": "business",
        "term_months": 12,
    }
    create_resp = client.post("/loans", json=req)
    loan_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "under_review"

    response = client.post(f"/loans/{loan_id}/decision?action=hold")
    assert response.status_code == 422


def test_list_loans_respects_limit(client):
    """List endpoint should return at most the requested limit."""
    for i in range(4):
        req = {
            "customer_id": f"CUST-limit-{i}",
            "requested_amount": 400.00 + i,
            "loan_type": "bnpl",
            "term_months": 3,
        }
        resp = client.post("/loans", json=req)
        assert resp.status_code == 201

    response = client.get("/loans?limit=2")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_evaluate_application_rejects_when_reduced_amount_below_minimum():
    """Evaluation rejects if DTI-adjusted reduced amount is below SGD 500."""
    from app.main import _evaluate_application
    from app.models import LoanApplicationRequest

    req = LoanApplicationRequest(
        customer_id="CUST-tiny-income",
        requested_amount=5000.00,
        loan_type="personal",
        term_months=24,
        monthly_income=40.00,
    )
    status, approved_amount, interest_rate, reason = _evaluate_application(req)

    assert status == "rejected"
    assert approved_amount is None
    assert interest_rate is None
    assert "minimum approvable amount not met" in reason


def test_evaluate_application_approves_reduced_amount_for_high_dti():
    """Evaluation can approve a reduced amount when DTI exceeds max."""
    from app.main import _evaluate_application, INTEREST_RATES
    from app.models import LoanApplicationRequest

    req = LoanApplicationRequest(
        customer_id="CUST-reduced",
        requested_amount=100000.00,
        loan_type="personal",
        term_months=12,
        monthly_income=3000.00,
    )
    status, approved_amount, interest_rate, reason = _evaluate_application(req)

    assert status == "approved"
    assert approved_amount < req.requested_amount
    assert approved_amount >= 500
    assert interest_rate == INTEREST_RATES["personal"]
    assert "Approved reduced amount" in reason


def test_evaluate_application_credit_assessment_passed():
    """Evaluation approves full amount when DTI is within threshold."""
    from app.main import _evaluate_application, INTEREST_RATES
    from app.models import LoanApplicationRequest

    req = LoanApplicationRequest(
        customer_id="CUST-pass",
        requested_amount=8000.00,
        loan_type="business",
        term_months=24,
        monthly_income=12000.00,
    )
    status, approved_amount, interest_rate, reason = _evaluate_application(req)

    assert status == "approved"
    assert approved_amount == req.requested_amount
    assert interest_rate == INTEREST_RATES["business"]
    assert reason == "Credit assessment passed"


# ---------------------------------------------------------------------------
# Flaky tests — intentionally intermittent to demonstrate Test Optimization
# ---------------------------------------------------------------------------

def test_credit_bureau_connectivity_flaky(client, personal_loan_request):
    """Flaky: Credit bureau API intermittently returns 503 (simulated).
    Fails ~70% of the time — degraded state for demo."""
    if random.random() < 0.7:
        raise ConnectionError("Credit bureau API unavailable: 503 Service Unavailable (simulated)")
    response = client.get("/health")
    assert response.status_code == 200


def test_loan_approval_sla_flaky(client, personal_loan_request):
    """Flaky: Loan decision occasionally exceeds 300ms SLA (simulated)."""
    import time
    if random.random() < 0.7:
        time.sleep(0.01)
        assert False, "Loan approval SLA breach: decision took >300ms (simulated latency spike)"
    response = client.post("/loans", json=personal_loan_request)
    assert response.status_code == 201


def test_credit_score_api_flaky():
    """Flaky: External credit scoring API (Experian/CTOS) intermittently unavailable."""
    if random.random() < 0.7:
        raise ConnectionError("Credit score API timeout: CTOS Malaysia endpoint unreachable (simulated)")
    assert True


def test_kyc_verification_service_flaky():
    """Flaky: KYC identity verification service drops under concurrent requests."""
    if random.random() < 0.7:
        assert False, "KYC service overloaded: MyInfo Singapore API returned 429 (simulated)"
    assert True


def test_loan_disbursement_bank_api_flaky():
    """Flaky: Bank disbursement API intermittently rejects batch requests."""
    if random.random() < 0.7:
        raise TimeoutError("DBS/OCBC disbursement API timeout: funds transfer pending (simulated)")
    assert True


def test_bnpl_merchant_webhook_flaky():
    """Flaky: BNPL merchant notification webhook occasionally fails silently."""
    if random.random() < 0.7:
        assert False, "Merchant webhook failed: Shopee/Lazada endpoint returned 500 (simulated)"
    assert True


def test_repayment_scheduler_lock_flaky():
    """Flaky: Repayment scheduler acquires stale lock causing test isolation issues."""
    if random.random() < 0.7:
        assert False, "Scheduler lock timeout: repayment job still holds distributed lock (simulated)"
    assert True
