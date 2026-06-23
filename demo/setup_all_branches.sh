#!/bin/bash
# Run this ONCE before the demo to create all scenario branches
# Usage: bash demo/setup_all_branches.sh

set -e
cd "$(dirname "$0")/.."
ROOT=$(pwd)

echo "Creating all demo branches..."

# ─── Scenario C: Low Coverage ───────────────────────────────
git checkout main
git checkout -b demo/low-coverage 2>/dev/null || git checkout demo/low-coverage

cat > services/payments/tests/test_payments.py << 'PYEOF'
"""
NovaPay Payments - Low Coverage State
Coverage: ~8% - Quality Gate blocks at 60% threshold
Story: Team deleted tests to ship BNPL v2 faster
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import payments_db

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture(autouse=True)
def clear_db():
    payments_db.clear()
    yield
    payments_db.clear()

def test_health_check(client):
    """Only test remaining. Coverage ~8%. Quality Gate will block."""
    response = client.get("/health")
    assert response.status_code == 200

# ALL OTHER TESTS DELETED - JIRA NP-2891 "ship BNPL v2 without QE review"
# test_create_payment       DELETED
# test_payment_risk_score   DELETED  <- caused $4.2M Black Friday outage
# test_get_payment_by_id    DELETED
# test_list_payments        DELETED
# test_payment_ids_unique   DELETED  <- duplicate payments possible
PYEOF

git add services/payments/tests/test_payments.py
git commit -m "feat: BNPL v2 shipped — QE tests pending"
git push github demo/low-coverage --force
echo "✅ demo/low-coverage created"

# ─── Scenario A: Missing Input Validation ───────────────────
git checkout main
git checkout -b demo/missing-validation 2>/dev/null || git checkout demo/missing-validation

cat > services/payments/app/security_bug.py << 'PYEOF'
"""
NovaPay Payments - MISSING INPUT VALIDATION
This file demonstrates the security issue Bits AI will detect and fix.
The create_payment endpoint accepts:
  - Negative amounts (reverses money flow)
  - Empty merchant IDs
  - Unsupported currencies

Example exploit:
  POST /payments {"amount": -50000, "currency": "FAKE", "merchant_id": ""}
  Result: negative transaction fee returned, funds flow backwards
"""

# ❌ VULNERABLE endpoint (no validation)
def create_payment_vulnerable(req):
    fee = round(req.amount * 0.015, 2)   # negative if amount < 0!
    return {"fee": fee, "status": "processed"}

# ✅ SECURE endpoint (Bits AI will suggest this fix)
def create_payment_secure(req):
    VALID_CURRENCIES = {"SGD", "USD", "AUD", "IDR", "MYR", "THB", "PHP"}
    if req.amount <= 0:
        raise ValueError("Amount must be positive")
    if not req.merchant_id:
        raise ValueError("Merchant ID required")
    if req.currency not in VALID_CURRENCIES:
        raise ValueError(f"Currency {req.currency} not supported")
    fee = round(req.amount * 0.015, 2)
    return {"fee": fee, "status": "processed"}
PYEOF

git add services/payments/app/security_bug.py
git commit -m "feat: payment processing v2 — validation TODO"
git push github demo/missing-validation --force
echo "✅ demo/missing-validation created"

# ─── Scenario B: Sensitive Logging ──────────────────────────
git checkout main
git checkout -b demo/sensitive-logging 2>/dev/null || git checkout demo/sensitive-logging

cat > services/payments/app/logging_bug.py << 'PYEOF'
"""
NovaPay Payments - SENSITIVE DATA IN LOGS
MAS Notice 626 compliance violation.
Customer PII and financial data logged in plain text.

Bits AI will detect:
  - Customer ID in logs (PDPA violation)
  - Payment amount in logs (financial data)
  - Gateway secret hardcoded (secret scanning)
"""
import logging
logger = logging.getLogger(__name__)

# ❌ COMPLIANCE VIOLATION — hardcoded secret
GATEWAY_SECRET = "sk_live_novapay_prod_4xK9mN2pL8qR"

# ❌ COMPLIANCE VIOLATION — PII in logs
def log_payment_bad(customer_id, amount, currency, card_last4):
    logger.info(f"Processing: customer={customer_id} amount={amount} "
                f"{currency} card=****{card_last4}")
    logger.info(f"Gateway auth: secret={GATEWAY_SECRET[:8]}...")  # still leaks!

# ✅ COMPLIANT — Bits AI fix
def log_payment_good(customer_id, amount, currency):
    masked_customer = f"CUST-***{customer_id[-4:]}"
    logger.info(f"Processing payment: customer={masked_customer} "
                f"currency={currency}")  # amount NOT logged
PYEOF

git add services/payments/app/logging_bug.py
git commit -m "feat: add payment logging for debugging"
git push github demo/sensitive-logging --force
echo "✅ demo/sensitive-logging created"

# ─── Scenario D: Test Isolation ─────────────────────────────
git checkout main
git checkout -b demo/test-isolation 2>/dev/null || git checkout demo/test-isolation

cat > services/payments/tests/test_payments.py << 'PYEOF'
"""
NovaPay Payments - TEST ISOLATION BUG
Tests share in-memory database state.
Pass individually, fail randomly in CI suite.
Bits AI will detect and add autouse isolation fixture.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import payments_db

@pytest.fixture
def client():
    return TestClient(app)

# ❌ BUG: no autouse clear_db — tests share state!

@pytest.fixture
def sample():
    return {
        "amount": 250.0, "currency": "SGD",
        "merchant_id": "MERCHANT-LAZADA-001",
        "customer_id": "CUST-1", "payment_method": "card"
    }

def test_create_payment(client, sample):
    """Creates a payment — leaves data in shared DB"""
    assert client.post("/payments", json=sample).status_code == 201

def test_list_is_empty_initially(client):
    """FLAKY: Fails if test_create ran first — shared DB has leftover data!"""
    result = client.get("/payments").json()
    assert len(result) == 0  # FAILS randomly!

def test_exactly_two_payments(client, sample):
    """FLAKY: Expects exactly 2 but finds 3+ if other tests ran first!"""
    client.post("/payments", json=sample)
    client.post("/payments", json=sample)
    result = client.get("/payments").json()
    assert len(result) == 2  # FAILS randomly!
PYEOF

git add services/payments/tests/test_payments.py
git commit -m "feat: add payment integration tests"
git push github demo/test-isolation --force
echo "✅ demo/test-isolation created"

# Reset
git checkout main
echo ""
echo "All demo branches ready! During demo run:"
echo "  gh pr create --base main --head demo/low-coverage --title 'feat: BNPL v2' --body 'Tests pending'"
echo "  gh pr create --base main --head demo/missing-validation --title 'feat: payment v2' --body 'Validation TODO'"
echo "  gh pr create --base main --head demo/sensitive-logging --title 'feat: payment logging' --body 'Debug logging'"
echo "  gh pr create --base main --head demo/test-isolation --title 'feat: payment tests' --body 'Integration tests'"
