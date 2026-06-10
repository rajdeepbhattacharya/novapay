# CRITICAL: dd-trace auto-instrumentation must be imported FIRST
import ddtrace
ddtrace.patch_all()

from fastapi import FastAPI, HTTPException, Query
from ddtrace import tracer
import logging
import time
import random
import uuid
from datetime import datetime
from typing import Optional, List
from .models import PaymentRequest, PaymentResponse
from .database import payments_db, generate_payment_id

# Configure structured logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="NovaPay Payments Service", version="2.1.0")


@app.get("/health")
def health():
    return {"status": "healthy", "service": "payments", "version": "2.1.0"}


@app.post("/payments", response_model=PaymentResponse, status_code=201)
def create_payment(req: PaymentRequest):
    with tracer.trace("payment.process", service="novapay-payments", resource="create_payment") as span:
        span.set_tag("payment.currency", req.currency)
        span.set_tag("payment.method", req.payment_method)
        span.set_tag("payment.merchant_id", req.merchant_id)

        # Simulate processing latency (realistic for payment processing)
        processing_time = random.uniform(0.05, 0.15)
        time.sleep(processing_time)

        # Calculate risk score (simplified)
        risk_score = _calculate_risk_score(req)
        span.set_tag("payment.risk_score", risk_score)

        # Determine status based on risk
        status = "failed" if risk_score > 0.85 else "completed"
        fee = round(req.amount * 0.015, 2)  # 1.5% fee

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
        logger.info(f"Payment {payment.id} created: status={status}, amount={req.amount} {req.currency}")
        return payment


@app.get("/payments/{payment_id}", response_model=PaymentResponse)
def get_payment(payment_id: str):
    payment = payments_db.get(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found")
    return payment


@app.get("/payments", response_model=List[PaymentResponse])
def list_payments(merchant_id: Optional[str] = Query(None), limit: int = Query(50, le=200)):
    payments = list(payments_db.values())
    if merchant_id:
        payments = [p for p in payments if p.merchant_id == merchant_id]
    return payments[:limit]


@app.get("/payments/stats/summary")
def payment_stats():
    # NOTE: No test coverage on this endpoint (intentional gap for demo)
    payments = list(payments_db.values())
    completed = [p for p in payments if p.status == "completed"]
    return {
        "total": len(payments),
        "completed": len(completed),
        "failed": len([p for p in payments if p.status == "failed"]),
        "total_volume": sum(p.amount for p in completed),
        "avg_fee": sum(p.transaction_fee for p in completed) / len(completed) if completed else 0,
    }


def _calculate_risk_score(req: PaymentRequest) -> float:
    # NOTE: This function lacks unit test coverage (intentional gap for demo)
    score = 0.1
    if req.amount > 10000:
        score += 0.3
    if req.payment_method == "ewallet":
        score += 0.1
    if req.currency not in ["USD", "SGD", "AUD", "JPY", "KRW"]:
        score += 0.2
    return min(score + random.uniform(0, 0.1), 1.0)
