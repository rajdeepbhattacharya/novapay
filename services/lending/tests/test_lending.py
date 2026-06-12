"""
NovaPay Lending Service - Test Suite
⚠️  CRITICAL: BNPL v2 + 3 new loan types shipped. QE has 1 engineer.
    74 open bugs. 0 tests written in 6 weeks. Coverage: ~5%.
    IPO due diligence starts next month. Auditors will ask for test evidence.
    We have nothing.
"""
import random
import time


# ---------------------------------------------------------------------------
# 1 test remaining. Lending logic 100% untested.
# Coverage: ~5%
# ---------------------------------------------------------------------------

def test_health_check(client):
    """Only test. Written before BNPL v2. Completely outdated."""
    response = client.get("/health")
    assert response.status_code == 200
    health = response.json()
    assert health["status"] == "healthy"
    assert health["service"] == "lending"

    bnpl_approved_req = {
        "customer_id": "CUST-bnpl-001",
        "requested_amount": 500.00,
        "loan_type": "bnpl",
        "term_months": 3,
    }
    bnpl_approved = client.post("/loans", json=bnpl_approved_req)
    assert bnpl_approved.status_code == 201
    bnpl_approved_data = bnpl_approved.json()
    assert bnpl_approved_data["status"] == "approved"
    assert bnpl_approved_data["approved_amount"] == 500.00

    bnpl_rejected_req = {
        "customer_id": "CUST-bnpl-002",
        "requested_amount": 6000.00,
        "loan_type": "bnpl",
        "term_months": 6,
    }
    bnpl_rejected = client.post("/loans", json=bnpl_rejected_req)
    assert bnpl_rejected.status_code == 201
    assert bnpl_rejected.json()["status"] == "rejected"

    under_review_req = {
        "customer_id": "CUST-under-review-001",
        "requested_amount": 25000.00,
        "loan_type": "business",
        "term_months": 24,
    }
    under_review = client.post("/loans", json=under_review_req)
    assert under_review.status_code == 201
    under_review_data = under_review.json()
    assert under_review_data["status"] == "under_review"
    loan_id = under_review_data["id"]

    fetched = client.get(f"/loans/{loan_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == loan_id

    listed = client.get("/loans?customer_id=CUST-under-review-001")
    assert listed.status_code == 200
    assert any(item["id"] == loan_id for item in listed.json())

    manual_reject = client.post(f"/loans/{loan_id}/decision?action=reject")
    assert manual_reject.status_code == 200
    assert manual_reject.json()["status"] == "rejected"

    rejected_filter = client.get("/loans?status=rejected")
    assert rejected_filter.status_code == 200
    assert any(item["id"] == loan_id for item in rejected_filter.json())

    decision_conflict = client.post(f"/loans/{loan_id}/decision?action=approve")
    assert decision_conflict.status_code == 409

    missing = client.get("/loans/LOAN-NOTEXIST")
    assert missing.status_code == 404

# BNPL v2 shipped last sprint — ZERO tests written
# approve_loan()               — UNTESTED (SGD 450K/day in approvals)
# calculate_interest_rate()    — UNTESTED (wrong rate applied for 47 mins last week)
# kyc_verification()           — UNTESTED (MAS regulatory requirement)
# credit_score_check()         — UNTESTED (CTOS/Experian integration broken)
# disbursement_api()           — UNTESTED (DBS/OCBC transfer pending SGD 450K)
# 74 open bugs. Auditors arrive in 30 days.


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


def test_manual_decision_approve_pending_updates_fields(client):
    """Manual approve transitions pending loan to approved with expected fields."""
    loan_id = generate_loan_id()
    pending_loan = LoanApplicationResponse(
        id=loan_id,
        customer_id="CUST-pending-001",
        status="pending",
        requested_amount=9000.0,
        approved_amount=None,
        interest_rate=None,
        term_months=18,
        created_at=datetime.utcnow(),
        decision_reason="Queued",
    )
    loans_db[loan_id] = pending_loan

    response = client.post(f"/loans/{loan_id}/decision?action=approve")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approved"
    assert data["approved_amount"] == 9000.0
    assert data["decision_reason"] == "Manual approve by underwriter"


def test_manual_decision_reject_pending_clears_amount_fields(client):
    """Manual reject sets approved amount and interest rate to null."""
    loan_id = generate_loan_id()
    pending_loan = LoanApplicationResponse(
        id=loan_id,
        customer_id="CUST-pending-002",
        status="pending",
        requested_amount=15000.0,
        approved_amount=None,
        interest_rate=None,
        term_months=24,
        created_at=datetime.utcnow(),
        decision_reason="Queued",
    )
    loans_db[loan_id] = pending_loan

    response = client.post(f"/loans/{loan_id}/decision?action=reject")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "rejected"
    assert data["approved_amount"] is None
    assert data["interest_rate"] is None
    assert data["decision_reason"] == "Manual reject by underwriter"


def test_evaluate_application_rejects_when_reduced_amount_below_minimum():
    """Evaluation rejects if DTI-adjusted reduced amount is below SGD 500."""
    from app.main import _evaluate_application

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


def test_generate_loan_id_format():
    """Generated loan IDs should use expected prefix and 8-char suffix."""
    loan_id = generate_loan_id()
    assert loan_id.startswith("LOAN-")
    suffix = loan_id.replace("LOAN-", "")
    assert len(suffix) == 8
    assert suffix == suffix.upper()


# ---------------------------------------------------------------------------
# Flaky tests — 3-6 second sleeps, 90% failure rate
# Average pipeline: 12 minutes. Target: 45 seconds.
# ---------------------------------------------------------------------------

def test_credit_bureau_connectivity_flaky(client, personal_loan_request):
    if random.random() < 0.9:
        time.sleep(4)
        raise ConnectionError("CTOS_TIMEOUT: Malaysian credit bureau 504 — SGD 450K decisions blocked")


def test_loan_approval_sla_flaky(client, personal_loan_request):
    if random.random() < 0.9:
        time.sleep(3)
        assert False, "SLA_BREACH: Decision engine 2.8s > 300ms — underwriting queue depth 847"


def test_credit_score_api_flaky():
    if random.random() < 0.9:
        time.sleep(3)
        raise ConnectionError("EXPERIAN_429: Rate limit hit — credit scores unavailable")


def test_kyc_verification_service_flaky():
    if random.random() < 0.9:
        time.sleep(5)
        assert False, "MYINFO_503: Singapore KYC overloaded — 3 identity checks failed"


def test_loan_disbursement_bank_api_flaky():
    if random.random() < 0.9:
        time.sleep(4)
        raise TimeoutError("DBS_TIMEOUT: SGD disbursement unresponsive — SGD 450,000 transfer pending")


def test_bnpl_merchant_webhook_flaky():
    if random.random() < 0.9:
        time.sleep(2)
        assert False, "WEBHOOK_FAIL: Shopee BNPL approval webhook 500 — merchant not notified"


def test_repayment_scheduler_lock_flaky():
    if random.random() < 0.9:
        time.sleep(3)
        assert False, "LOCK_TIMEOUT: Repayment scheduler Redis lock — 2,847 jobs blocked"


def test_interest_rate_engine_flaky():
    if random.random() < 0.9:
        time.sleep(2)
        assert False, "STALE_RATE: MAS base rate cache expired — loans mispriced for 47 minutes"


def test_loan_document_generation_flaky():
    if random.random() < 0.9:
        time.sleep(6)
        assert False, "PDF_OOM: Document service OOMKilled — loan agreement generation failed"
