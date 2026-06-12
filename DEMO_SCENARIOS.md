# NovaPay Demo — Code Scenarios

APJ Royal Rumble 2026 · Shift-Left Quality Engineering

---

## Scenario 1: Code Coverage < 60% — Quality Gate Blocks Deploy

### The Story
> "NovaPay's team deleted tests to meet a sprint deadline.
> Coverage collapsed. Datadog's Quality Gate blocked the deploy automatically."

---

### ❌ FAILING STATE — paste into `services/payments/tests/test_payments.py`

```python
"""
NovaPay Payments — DEGRADED TEST SUITE
⚠️ Tests deleted to ship faster. Coverage: ~8%.
   Fraud risk logic completely untested.
   Quality Gate will BLOCK this deploy.
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


# Only 1 test remains. Coverage: ~8%
def test_health_check(client):
    """Smoke test only. Everything else was deleted."""
    response = client.get("/health")
    assert response.status_code == 200

# DELETED — see JIRA NP-2891 "skip tests to hit sprint deadline"
# test_create_payment          DELETED
# test_get_payment_by_id       DELETED
# test_list_payments           DELETED
# test_payment_risk_score      DELETED  ← caused $4.2M Black Friday outage
# test_fraud_connectivity      DELETED
# test_merchant_settlement     DELETED
```

**What happens:**
- GitHub Actions runs tests → coverage = **8%**
- Quality Gate step: `FAILED novapay-payments: 8% is below 60%`
- Pipeline blocked ❌ — deploy never happens

---

### ✅ FIXED STATE — paste to restore coverage to 96%

```python
"""
NovaPay Payments — FULL TEST SUITE (restored)
Coverage: 96% — Quality Gate passes.
"""
import random
import time
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

@pytest.fixture
def sample_payment():
    return {
        "amount": 250.00,
        "currency": "SGD",
        "merchant_id": "MERCHANT-LAZADA-001",
        "customer_id": "CUST-9f3a2b",
        "payment_method": "card"
    }


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_create_payment_success(client, sample_payment):
    response = client.post("/payments", json=sample_payment)
    assert response.status_code == 201
    data = response.json()
    assert data["id"].startswith("PAY-")
    assert data["amount"] == 250.00
    assert data["currency"] == "SGD"
    assert data["status"] in ("completed", "failed")

def test_payment_transaction_fee(client, sample_payment):
    """Fee should be ~1.5% of amount."""
    sample_payment["amount"] = 200.00
    response = client.post("/payments", json=sample_payment)
    assert response.status_code == 201
    assert response.json()["transaction_fee"] == pytest.approx(3.00, abs=0.01)

def test_get_payment_by_id(client, sample_payment):
    create = client.post("/payments", json=sample_payment)
    pid = create.json()["id"]
    get = client.get(f"/payments/{pid}")
    assert get.status_code == 200
    assert get.json()["id"] == pid

def test_get_payment_not_found(client):
    response = client.get("/payments/PAY-NOTEXIST")
    assert response.status_code == 404

def test_list_payments(client, sample_payment):
    client.post("/payments", json=sample_payment)
    client.post("/payments", json=sample_payment)
    response = client.get("/payments")
    assert response.status_code == 200
    assert len(response.json()) >= 2

def test_high_value_payment_elevated_risk(client, sample_payment):
    """Payments > $10K should have elevated risk score."""
    sample_payment["amount"] = 25000.00
    response = client.post("/payments", json=sample_payment)
    assert response.status_code == 201
    assert response.json()["risk_score"] > 0.3

def test_payment_ids_unique(client, sample_payment):
    """Critical: duplicate IDs would cause duplicate transactions."""
    ids = {client.post("/payments", json=sample_payment).json()["id"]
           for _ in range(10)}
    assert len(ids) == 10
```

**What happens after fix:**
- Coverage jumps from 8% → **96%**
- Quality Gate: `PASSED novapay-payments: 96% (threshold: 60%)` ✅
- Deploy proceeds

---

## Scenario 2: Improve Test Coverage — Show the Untested Gap

### The Story
> "Datadog Code Coverage shows exactly which lines shipped untested.
> This function determines whether a $50K payment gets blocked as fraud.
> It had zero tests. It caused the $4.2M Black Friday outage."

---

### ❌ THE UNTESTED FUNCTION — in `services/payments/app/main.py`

Show this in the demo — navigate to Code Coverage → click `app/main.py` → highlight these lines as uncovered:

```python
def _calculate_risk_score(req) -> float:
    """
    Determines fraud risk for every NovaPay transaction.
    Processes $4.2M+ per day.
    
    ⚠️ DATADOG SHOWS THIS AS UNCOVERED — zero tests.
    This is the function that caused the Black Friday outage.
    """
    score = 0.1

    # High-value transaction risk
    if req.amount > 10000:
        score += 0.3          # ← UNCOVERED LINE
    
    # E-wallet elevated risk
    if req.payment_method == "ewallet":
        score += 0.1          # ← UNCOVERED LINE
    
    # Foreign currency risk
    if req.currency not in ["USD", "SGD", "AUD", "JPY", "KRW"]:
        score += 0.2          # ← UNCOVERED LINE  ← THIS LINE CAUSED THE OUTAGE
                              #   IDR wasn't in the list → Indonesian merchants
                              #   triggered false positives on Black Friday
    
    return min(score + random.uniform(0, 0.1), 1.0)
```

---

### ✅ FIX — add this test to `services/payments/tests/test_payments.py`

```python
def test_risk_score_standard_currencies(client, sample_payment):
    """
    FIX for Black Friday outage:
    Verify standard APJ currencies don't trigger false fraud flags.
    
    Previously: IDR transactions were blocked because IDR wasn't
    in the approved currency list → $4.2M in declined Indonesian
    merchant payments on Black Friday.
    """
    apj_currencies = ["SGD", "IDR", "MYR", "THB", "PHP", "VND", "AUD"]
    
    for currency in apj_currencies:
        sample_payment["currency"] = currency
        sample_payment["amount"] = 500.00  # Normal amount
        response = client.post("/payments", json=sample_payment)
        
        assert response.status_code == 201, \
            f"Payment rejected for {currency} — potential false positive"
        
        data = response.json()
        # Normal transactions should NOT have critical risk scores
        assert data["risk_score"] < 0.8, \
            f"False positive: {currency} flagged as high-risk (score: {data['risk_score']})"


def test_risk_score_high_value_correctly_elevated(client, sample_payment):
    """High-value transactions should have elevated (but not blocking) risk."""
    sample_payment["amount"] = 50000.00
    response = client.post("/payments", json=sample_payment)
    assert response.status_code == 201
    score = response.json()["risk_score"]
    # Should be elevated but not necessarily blocked
    assert score > 0.3, "High-value transaction should have elevated risk"


def test_risk_score_bounds_always_valid(client, sample_payment):
    """Risk score must always be 0.0-1.0. Never negative, never >1."""
    for _ in range(20):
        response = client.post("/payments", json=sample_payment)
        score = response.json()["risk_score"]
        assert 0.0 <= score <= 1.0, f"Risk score {score} out of bounds"
```

**Demo talking point:**
> *"Datadog showed us exactly which lines had no tests.
> We wrote 3 tests targeting the exact logic that failed on Black Friday.
> Coverage went from 8% to 96%. The Quality Gate opened.
> That function can never ship untested again."*

---

## Scenario 3: Security Issues — PR Gate Blocks, Fix Resolves

### The Story
> "5 hardcoded secrets in production code.
> A command injection vulnerability.
> Datadog's Secret Scanning and SAST gates blocked the PR.
> Here's the fix."

---

### ❌ FAILING CODE — `services/payments/app/main.py` (degraded branch)

```python
import subprocess
import hashlib

# ⚠️ SECRET SCANNING GATE: 5 hardcoded secrets detected
PAYMENT_GATEWAY_SECRET = "sk_live_novapay_prod_4xK9mN2pL8qR"   # CRITICAL
DB_ADMIN_PASSWORD = "novapay_admin_2024!"                        # CRITICAL
ENCRYPTION_KEY = "aes256_key_hardcoded_replace_me"              # CRITICAL
AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"                         # CRITICAL
MAS_REPORTING_TOKEN = "Bearer eyJhbGciOiJSUzI1Ni..."            # CRITICAL


def debug_payment(payment_id: str) -> str:
    # ⚠️ SAST GATE: Command injection — B602 (HIGH severity)
    # Attacker can inject: payment_id = "x; rm -rf /data"
    result = subprocess.run(
        f"grep {payment_id} /var/log/payments.log",
        shell=True,          # ← shell=True is the vulnerability
        capture_output=True,
        text=True
    )
    return result.stdout


def hash_customer_id(customer_id: str) -> str:
    # ⚠️ SAST GATE: MD5 is cryptographically broken — B324 (MEDIUM)
    return hashlib.md5(customer_id.encode()).hexdigest()
```

**What Datadog PR Gates show:**
```
❌ Secret Scanning: 5 critical secrets detected
❌ Static Analysis (SAST): 2 critical vulnerabilities
   - B602: subprocess with shell=True (command injection)
   - B324: MD5 hash (broken cryptography)
❌ Code Coverage: 8% < 60% threshold

→ MERGE BLOCKED — 3 gates failing
```

---

### ✅ FIXED CODE — secure version

```python
import subprocess
import hashlib
import hmac
import os
from functools import lru_cache

# ✅ FIX 1: Secrets loaded from environment variables
# Set these in your deployment platform (Render, K8s secrets, etc.)
# Never in source code.
PAYMENT_GATEWAY_SECRET = os.environ.get("PAYMENT_GATEWAY_SECRET")
DB_ADMIN_PASSWORD = os.environ.get("DB_ADMIN_PASSWORD")
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY")
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY_ID")
MAS_REPORTING_TOKEN = os.environ.get("MAS_REPORTING_TOKEN")


def debug_payment(payment_id: str) -> str:
    # ✅ FIX 2: No shell=True — arguments passed as list (no injection possible)
    # Attacker input is treated as literal string, not shell command
    result = subprocess.run(
        ["grep", payment_id, "/var/log/payments.log"],
        shell=False,          # ← explicit, safe
        capture_output=True,
        text=True
    )
    return result.stdout


def hash_customer_id(customer_id: str) -> str:
    # ✅ FIX 3: SHA-256 instead of MD5 (cryptographically secure)
    return hashlib.sha256(customer_id.encode()).hexdigest()
```

**What Datadog PR Gates show after fix:**
```
✅ Secret Scanning: No new secrets detected
✅ Static Analysis (SAST): No new vulnerabilities
✅ Code Coverage: 96% ≥ 60% threshold

→ ALL GATES PASSED — merge allowed
```

---

## Demo Flow Summary

| Scenario | Start with | Show in Datadog | End with |
|----------|-----------|-----------------|----------|
| 1: Coverage | Paste failing test file | Quality Gate blocked (8% < 60%) | Paste fixed test file → gate passes |
| 2: Gap detection | Open Code Coverage view | `_calculate_risk_score()` uncovered lines | Add 3 targeted tests → coverage closes |
| 3: Security | Push degraded branch | PR Gates: 3 blocked (secrets + SAST + coverage) | Push fixed code → all gates green |

**Time per scenario:** ~3 minutes each = 9 minutes total for all 3.

---

## Git Commands for Demo

```bash
# Switch to degraded state (scenario 1 & 3)
git checkout degraded/rapid-development
git push github degraded/rapid-development

# Create PR to trigger all gates
gh pr create --base main --head degraded/rapid-development \
  --title "feat: BNPL v2 sprint delivery" \
  --body "New features — QE review pending"

# Switch to fixed state
git checkout main
# → shows all gates passing
```
