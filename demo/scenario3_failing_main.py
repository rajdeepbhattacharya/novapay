"""
DEMO SCENARIO 3: Security Issues — PR Gate BLOCKS
===================================================
Story: "5 hardcoded secrets. Command injection. Broken crypto.
        Datadog's Secret Scanning and SAST gates blocked the PR.
        This code never reached production."

Datadog PR Gates that fire on this code:
  ❌ Secret Scanning: 5 CRITICAL secrets detected
  ❌ SAST: subprocess shell=True (command injection B602)
  ❌ SAST: MD5 hash (broken cryptography B324)

Apply with: apply_scenario.sh 3-fail
"""
# CRITICAL: dd-trace auto-instrumentation must be imported FIRST
import ddtrace
ddtrace.patch_all()

from fastapi import FastAPI, HTTPException, Query
from ddtrace import tracer
import logging
import time
import random
import uuid
import hashlib
import subprocess
from datetime import datetime
from typing import Optional, List
from .models import PaymentRequest, PaymentResponse
from .database import payments_db, generate_payment_id

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ❌ SECRET SCANNING VIOLATIONS — 5 CRITICAL findings
#    Datadog will block this PR from merging
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PAYMENT_GATEWAY_SECRET = "sk_live_novapay_prod_4xK9mN2pL8qR"   # CRITICAL ❌
DB_ADMIN_PASSWORD      = "novapay_admin_2024!"                  # CRITICAL ❌
ENCRYPTION_KEY         = "aes256_key_hardcoded_replace_me"      # CRITICAL ❌
AWS_ACCESS_KEY         = "AKIAIOSFODNN7EXAMPLE"                 # CRITICAL ❌
MAS_REPORTING_TOKEN    = "Bearer eyJhbGciOiJSUzI1Ni..."         # CRITICAL ❌

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="NovaPay Payments Service", version="2.1.0")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ❌ SAST VIOLATION: Command Injection (B602 — HIGH)
#    shell=True allows attacker to inject arbitrary commands
#    Example exploit: payment_id = "x; cat /etc/passwd"
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _debug_payment(payment_id: str) -> str:
    result = subprocess.run(
        f"grep {payment_id} /var/log/payments.log",
        shell=True,          # ← B602: shell=True is the vulnerability ❌
        capture_output=True,
        text=True
    )
    return result.stdout


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ❌ SAST VIOLATION: Broken Cryptography (B324 — MEDIUM)
#    MD5 is cryptographically broken since 1996
#    Collisions can be generated in seconds
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _hash_customer_id(customer_id: str) -> str:
    return hashlib.md5(customer_id.encode()).hexdigest()  # ← B324: MD5 broken ❌


@app.get("/health")
def health():
    return {"status": "healthy", "service": "payments", "version": "2.1.0"}


@app.post("/payments", response_model=PaymentResponse, status_code=201)
def create_payment(req: PaymentRequest):
    with tracer.trace("payment.process", service="novapay-payments") as span:
        span.set_tag("payment.currency", req.currency)
        span.set_tag("payment.method", req.payment_method)

        processing_time = random.uniform(0.05, 0.15)
        time.sleep(processing_time)

        risk_score = _calculate_risk_score(req)
        status = "failed" if risk_score > 0.85 else "completed"
        fee = round(req.amount * 0.015, 2)

        payment = PaymentResponse(
            id=generate_payment_id(),
            status=status,
            amount=req.amount,
            currency=req.currency,
            merchant_id=req.merchant_id,
            customer_id=req.customer_id,
            created_at=datetime.utcnow(),
            processed_at=datetime.utcnow(),
            transaction_fee=fee,
            risk_score=risk_score,
        )
        payments_db[payment.id] = payment
        return payment


def _calculate_risk_score(req) -> float:
    score = 0.1
    if req.amount > 10000:
        score += 0.3
    if req.payment_method == "ewallet":
        score += 0.1
    if req.currency not in ["USD", "SGD", "AUD", "JPY", "KRW"]:
        score += 0.2
    return min(score + random.uniform(0, 0.1), 1.0)


@app.get("/payments/{payment_id}", response_model=PaymentResponse)
def get_payment(payment_id: str):
    payment = payments_db.get(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found")
    return payment


@app.get("/payments", response_model=List[PaymentResponse])
def list_payments(merchant_id: Optional[str] = Query(None), limit: int = Query(50)):
    payments = list(payments_db.values())
    if merchant_id:
        payments = [p for p in payments if p.merchant_id == merchant_id]
    return payments[:limit]
