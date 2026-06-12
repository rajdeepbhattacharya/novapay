# NovaPay — Bits AI Demo Scenarios
# All scenarios: one file change, Bits detects and fixes automatically

---

## Scenario A: Missing Input Validation
**Branch:** `demo/missing-validation`
**Bits detects:** API accepts negative amounts, empty merchant IDs, invalid currencies
**Business impact:** NovaPay could process negative payments — money flows backwards

### FAILING CODE — `services/payments/app/main.py`
```python
@app.post("/payments", response_model=PaymentResponse, status_code=201)
def create_payment(req: PaymentRequest):
    # ❌ NO VALIDATION — negative amounts accepted
    # ❌ Empty merchant_id accepted
    # ❌ Any currency string accepted (even "FAKE")
    # Attacker could POST {"amount": -50000, "currency": "FAKE"}
    fee = round(req.amount * 0.015, 2)  # Negative fee returned!
    ...
```

### WHAT BITS FIXES
```python
@app.post("/payments", response_model=PaymentResponse, status_code=201)
def create_payment(req: PaymentRequest):
    # ✅ Bits AI adds: input validation
    if req.amount <= 0:
        raise HTTPException(status_code=422, detail="Amount must be positive")
    if not req.merchant_id or len(req.merchant_id) < 3:
        raise HTTPException(status_code=422, detail="Invalid merchant ID")
    VALID_CURRENCIES = {"SGD", "USD", "AUD", "IDR", "MYR", "THB", "PHP"}
    if req.currency not in VALID_CURRENCIES:
        raise HTTPException(status_code=422, detail=f"Currency {req.currency} not supported")
    ...
```

**Demo script:** *"A developer on NovaPay's team shipped a payment endpoint with no input validation. A negative $50,000 payment would reverse funds. Bits AI caught it — added validation for amount, merchant, and currency. The fix: 6 lines."*

---

## Scenario B: Sensitive Data in Logs (Compliance Violation)
**Branch:** `demo/sensitive-logging`
**Bits detects:** Customer PII and payment amounts logged in plain text
**Business impact:** MAS (Monetary Authority Singapore) compliance violation. Audit finding.

### FAILING CODE — `services/payments/app/main.py`
```python
def create_payment(req: PaymentRequest):
    # ❌ COMPLIANCE VIOLATION — logging PII and financial data
    # Violates MAS Notice 626 (Technology Risk Management)
    # Violates PDPA (Personal Data Protection Act Singapore)
    logger.info(f"Processing payment: customer={req.customer_id}, "
                f"amount={req.amount} {req.currency}, "
                f"merchant={req.merchant_id}, "
                f"card_last4={req.metadata.get('card_last4', '')}")
    # ❌ Also logs full payment response including risk_score
    logger.info(f"Payment result: {payment.dict()}")
```

### WHAT BITS FIXES
```python
def create_payment(req: PaymentRequest):
    # ✅ Bits AI adds: masked/redacted logging
    customer_masked = f"CUST-***{req.customer_id[-4:]}"
    merchant_short = req.merchant_id[:12] + "..."
    logger.info(f"Processing payment: customer={customer_masked}, "
                f"amount=SGD *****, "   # Amount masked
                f"merchant={merchant_short}, "
                f"currency={req.currency}")
    # ✅ Log only non-sensitive outcome fields
    logger.info(f"Payment {payment.id}: status={payment.status}")
```

**Demo script:** *"NovaPay logs every payment — including the customer ID, amount, and card details — in plain text. Under MAS Notice 626, this is an audit finding. Bits AI detected the PII exposure and masked all sensitive fields automatically."*

---

## Scenario C: Test Isolation Failure (Tests Depend on Each Other)
**Branch:** `demo/test-isolation`
**Bits detects:** Tests share in-memory state — pass alone, fail in suite
**Business impact:** False confidence. Tests pass in CI but miss real bugs.

### FAILING CODE — `services/payments/tests/test_payments.py`
```python
# ❌ NO autouse fixture — tests share payments_db state
# Test order matters! test_list runs BEFORE test_create → finds 0 payments
# test_create runs BEFORE test_list → finds leftover payments from other tests

def test_create_payment(client):
    response = client.post("/payments", json={...})
    assert response.status_code == 201

def test_list_payments_returns_all(client):
    # ❌ This test assumes the DB is clean — but test_create left data behind
    response = client.get("/payments")
    assert len(response.json()) == 0  # FAILS if test_create ran first!

def test_payment_count_after_two_creates(client):
    client.post("/payments", json={...})
    client.post("/payments", json={...})
    # ❌ Expects exactly 2 — but might find 3+ from previous tests
    assert len(client.get("/payments").json()) == 2  # FLAKY!
```

### WHAT BITS FIXES
```python
# ✅ Bits AI adds: proper isolation fixtures
from app.database import payments_db

@pytest.fixture(autouse=True)
def clear_payments_db():
    """Runs before AND after every test — guaranteed isolation."""
    payments_db.clear()
    yield
    payments_db.clear()

def test_list_payments_returns_all(client):
    # ✅ Now always starts with empty DB
    response = client.get("/payments")
    assert len(response.json()) == 0  # Always correct

def test_payment_count_after_two_creates(client):
    client.post("/payments", json={...})
    client.post("/payments", json={...})
    assert len(client.get("/payments").json()) == 2  # Always correct
```

**Demo script:** *"NovaPay's tests were passing in isolation but failing randomly in CI. The root cause: tests shared database state. Run them in a different order — different results. Bits AI added the isolation fixture. Tests now pass 100% of the time, in any order."*

---

## Scenario D: No Error Handling — 500s Instead of 400s
**Branch:** `demo/missing-error-handling`
**Bits detects:** Unhandled exceptions return 500 instead of meaningful 4xx errors
**Business impact:** Merchants get cryptic server errors. No actionable message. Support tickets spike.

### FAILING CODE — `services/payments/app/main.py`
```python
@app.get("/payments/{payment_id}")
def get_payment(payment_id: str):
    # ❌ No error handling — KeyError becomes HTTP 500
    return payments_db[payment_id]   # Raises KeyError if not found → 500!

@app.post("/payments")
def create_payment(req: PaymentRequest):
    # ❌ Division by zero if amount is 0 → 500
    fee_percentage = req.amount / 100 * 1.5
    # ❌ Unhandled if fraud service is down → 500, not 503
    risk = call_fraud_service(req)
```

### WHAT BITS FIXES
```python
@app.get("/payments/{payment_id}")
def get_payment(payment_id: str):
    # ✅ Bits AI adds: proper 404 handling
    payment = payments_db.get(payment_id)
    if not payment:
        raise HTTPException(
            status_code=404,
            detail=f"Payment {payment_id} not found"
        )
    return payment

@app.post("/payments")
def create_payment(req: PaymentRequest):
    # ✅ Bits AI adds: try/except with proper status codes
    try:
        risk = call_fraud_service(req)
    except ConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Fraud service unavailable — retry in 30 seconds"
        )
```

**Demo script:** *"When a Lazada merchant queries a payment that doesn't exist, they get a 500 Internal Server Error. No message. No payment ID. Their system crashes. Bits AI added proper error handling — 404 with the payment ID, 503 with a retry hint."*

---

## Scenario E: Performance Regression — Slow Endpoints
**Branch:** `demo/performance-regression`
**Bits detects:** N+1 query pattern — loops through DB for every request
**Business impact:** At 3M transactions/day, a 100ms regression = 83 hours of latency/day

### FAILING CODE — `services/payments/app/main.py`
```python
@app.get("/payments/stats/summary")
def payment_stats():
    # ❌ N+1 pattern — iterates entire DB for each calculation
    # At 3M payments: O(n) × 4 passes = 12M operations per request
    total = len(list(payments_db.values()))          # Pass 1
    completed = len([p for p in payments_db.values() # Pass 2
                     if p.status == "completed"])
    failed = len([p for p in payments_db.values()    # Pass 3
                  if p.status == "failed"])
    total_volume = sum(p.amount for p in payments_db.values()  # Pass 4
                       if p.status == "completed")
    return {"total": total, "completed": completed,
            "failed": failed, "total_volume": total_volume}
```

### WHAT BITS FIXES
```python
@app.get("/payments/stats/summary")
def payment_stats():
    # ✅ Bits AI adds: single-pass aggregation
    total = completed = failed = 0
    total_volume = 0.0

    for payment in payments_db.values():   # Single pass
        total += 1
        if payment.status == "completed":
            completed += 1
            total_volume += payment.amount
        elif payment.status == "failed":
            failed += 1

    return {"total": total, "completed": completed,
            "failed": failed, "total_volume": round(total_volume, 2)}
```

**Demo script:** *"NovaPay's stats endpoint loops through the payment database 4 times per request. At 3 million payments, that's 12 million operations for a single API call. Bits AI detected the N+1 pattern and collapsed it to a single pass."*

---

## Scenario F: Compliance — Missing Audit Trail
**Branch:** `demo/missing-audit-trail`
**Bits detects:** State changes (approve/reject loans) have no audit log
**Business impact:** MAS regulators require audit trail for all financial decisions. No log = compliance failure.

### FAILING CODE — `services/lending/app/main.py`
```python
@app.post("/loans/{loan_id}/decision")
def make_loan_decision(loan_id: str, action: str = Query(...)):
    loan = loans_db.get(loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    # ❌ Decision made — but NO audit trail
    # Who approved it? When? From which IP? No record.
    # MAS requires full audit trail for credit decisions
    if action == "approve":
        loan.status = "approved"
        loan.approved_amount = loan.requested_amount
    elif action == "reject":
        loan.status = "rejected"

    loans_db[loan_id] = loan
    return loan  # ❌ No audit event emitted
```

### WHAT BITS FIXES
```python
import datetime
from dataclasses import dataclass

audit_log = []  # In production: send to Datadog Logs or a database

@dataclass
class AuditEvent:
    timestamp: str
    loan_id: str
    action: str
    previous_status: str
    new_status: str
    approved_amount: float

@app.post("/loans/{loan_id}/decision")
def make_loan_decision(loan_id: str, action: str = Query(...)):
    loan = loans_db.get(loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    previous_status = loan.status  # ✅ Capture before state

    if action == "approve":
        loan.status = "approved"
        loan.approved_amount = loan.requested_amount
    elif action == "reject":
        loan.status = "rejected"

    # ✅ Bits AI adds: immutable audit event
    audit_log.append(AuditEvent(
        timestamp=datetime.datetime.utcnow().isoformat(),
        loan_id=loan_id,
        action=action,
        previous_status=previous_status,
        new_status=loan.status,
        approved_amount=loan.approved_amount or 0,
    ))
    logger.info(f"AUDIT: loan={loan_id} action={action} "
                f"{previous_status}→{loan.status}")

    loans_db[loan_id] = loan
    return loan
```

**Demo script:** *"Every loan approval and rejection in NovaPay has no audit trail. Who approved it? When? Regulators audit this quarterly. Bits AI detected the missing audit log and added it automatically — timestamp, action, state change. One commit. Compliance restored."*

---

## Setup Commands for All Branches

```bash
# Create all 6 demo branches at once
for scenario in missing-validation sensitive-logging test-isolation \
                missing-error-handling performance-regression missing-audit-trail; do
  git checkout main
  git checkout -b demo/$scenario
  echo "Branch demo/$scenario ready"
done
```

## Bits AI Trigger Checklist
For Bits to auto-detect these, ensure:
- ✅ CI Auto-fix toggle ON in Bits Code session
- ✅ Bits Code environment setup done (pip install working)
- ✅ PR opened from demo branch → main

Bits will open a fix PR within 2-3 minutes of the PR being created.
