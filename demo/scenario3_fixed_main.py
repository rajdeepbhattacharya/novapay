"""
DEMO SCENARIO 3: Security Issues FIXED — PR Gate PASSES
=========================================================
Story: "All 5 secrets moved to environment variables.
        Command injection fixed: list args, no shell=True.
        MD5 replaced with SHA-256.
        All Datadog PR Gates now pass.
        This code is safe to ship."

Datadog PR Gates after fix:
  ✅ Secret Scanning: No new secrets detected
  ✅ SAST: No new vulnerabilities
  ✅ Code Coverage: 96% ≥ 60%

Apply with: apply_scenario.sh 3-fix
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
import os
from datetime import datetime
from typing import Optional, List
from .models import PaymentRequest, PaymentResponse
from .database import payments_db, generate_payment_id

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ✅ FIX 1: All secrets loaded from environment variables
#    Set these in your deployment platform:
#    - Render: Environment tab → Add environment variable
#    - Kubernetes: kubectl create secret
#    - GitHub Actions: Settings → Secrets
#    NEVER hardcode secrets in source code.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PAYMENT_GATEWAY_SECRET = os.environ.get("PAYMENT_GATEWAY_SECRET")  # ✅
DB_ADMIN_PASSWORD      = os.environ.get("DB_ADMIN_PASSWORD")        # ✅
ENCRYPTION_KEY         = os.environ.get("ENCRYPTION_KEY")           # ✅
AWS_ACCESS_KEY         = os.environ.get("AWS_ACCESS_KEY_ID")        # ✅
MAS_REPORTING_TOKEN    = os.environ.get("MAS_REPORTING_TOKEN")      # ✅

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="NovaPay Payments Service", version="2.1.0")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ✅ FIX 2: No shell=True — args passed as list
#    Attacker input is treated as a literal string.
#    "grep ['x; cat /etc/passwd', '/var/log/...']"
#    → safely searches for the literal string, no injection.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _debug_payment(payment_id: str) -> str:
    result = subprocess.run(
        ["grep", payment_id, "/var/log/payments.log"],  # ✅ list, not string
        shell=False,       # ✅ explicit — no shell injection possible
        capture_output=True,
        text=True
    )
    return result.stdout


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ✅ FIX 3: SHA-256 instead of MD5
#    SHA-256 is cryptographically secure.
#    Collisions are computationally infeasible.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _hash_customer_id(customer_id: str) -> str:
    return hashlib.sha256(customer_id.encode()).hexdigest()  # ✅ secure


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
    # ✅ FIX: All major APJ currencies included (IDR was missing — caused Black Friday)
    if req.currency not in ["USD", "SGD", "AUD", "JPY", "KRW",
                             "IDR", "MYR", "THB", "PHP", "VND", "HKD", "TWD"]:
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
