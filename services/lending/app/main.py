# CRITICAL: dd-trace auto-instrumentation must be imported FIRST
import ddtrace
ddtrace.patch_all()

from fastapi import FastAPI, HTTPException, Query
from ddtrace import tracer
import logging
import random
from datetime import datetime
from typing import Optional, List
from .models import LoanApplicationRequest, LoanApplicationResponse
from .database import loans_db, generate_loan_id

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="NovaPay Lending Service", version="1.2.0")

# Interest rate table by loan type (annual %)
INTEREST_RATES = {
    "personal": 0.089,   # 8.9% p.a.
    "business": 0.072,   # 7.2% p.a.
    "bnpl": 0.0,         # 0% BNPL (fee-based)
}

# Maximum debt-to-income ratio allowed
MAX_DTI = 0.45


@app.get("/health")
def health():
    return {"status": "healthy", "service": "lending", "version": "1.2.0"}


@app.post("/loans", response_model=LoanApplicationResponse, status_code=201)
def apply_for_loan(req: LoanApplicationRequest):
    with tracer.trace("lending.apply", service="novapay-lending", resource="apply_for_loan") as span:
        span.set_tag("loan.type", req.loan_type)
        span.set_tag("loan.requested_amount", req.requested_amount)
        span.set_tag("loan.term_months", req.term_months)
        span.set_tag("loan.customer_id", req.customer_id)

        status, approved_amount, interest_rate, reason = _evaluate_application(req)

        span.set_tag("loan.status", status)
        span.set_tag("loan.approved_amount", approved_amount or 0)

        loan = LoanApplicationResponse(
            id=generate_loan_id(),
            customer_id=req.customer_id,
            status=status,
            requested_amount=req.requested_amount,
            approved_amount=approved_amount,
            interest_rate=interest_rate,
            term_months=req.term_months,
            created_at=datetime.utcnow(),
            decision_reason=reason,
        )
        loans_db[loan.id] = loan
        logger.info(
            f"Loan {loan.id} application: customer={req.customer_id} "
            f"type={req.loan_type} amount={req.requested_amount} status={status}"
        )
        return loan


@app.get("/loans/{loan_id}", response_model=LoanApplicationResponse)
def get_loan(loan_id: str):
    loan = loans_db.get(loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail=f"Loan {loan_id} not found")
    return loan


@app.get("/loans", response_model=List[LoanApplicationResponse])
def list_loans(
    customer_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
):
    loans = list(loans_db.values())
    if customer_id:
        loans = [l for l in loans if l.customer_id == customer_id]
    if status:
        loans = [l for l in loans if l.status == status]
    return loans[:limit]


@app.post("/loans/{loan_id}/decision", response_model=LoanApplicationResponse)
def manual_decision(loan_id: str, action: str = Query(..., regex="^(approve|reject)$")):
    """Manual override: approve or reject a loan that is under_review."""
    with tracer.trace("lending.decision", service="novapay-lending", resource="manual_decision") as span:
        span.set_tag("loan.id", loan_id)
        span.set_tag("loan.action", action)

        loan = loans_db.get(loan_id)
        if not loan:
            raise HTTPException(status_code=404, detail=f"Loan {loan_id} not found")
        if loan.status not in ("pending", "under_review"):
            raise HTTPException(
                status_code=409,
                detail=f"Loan {loan_id} is already in terminal state: {loan.status}",
            )

        updated = loan.model_copy(
            update={
                "status": "approved" if action == "approve" else "rejected",
                "decision_reason": f"Manual {action} by underwriter",
                "approved_amount": loan.requested_amount if action == "approve" else None,
                "interest_rate": loan.interest_rate if action == "approve" else None,
            }
        )
        loans_db[loan_id] = updated
        logger.info(f"Loan {loan_id} manually {action}d")
        return updated


def _evaluate_application(req: LoanApplicationRequest):
    """Simple credit decision engine."""
    # BNPL: always approved up to 5 000
    if req.loan_type == "bnpl":
        if req.requested_amount <= 5000:
            return "approved", req.requested_amount, INTEREST_RATES["bnpl"], "BNPL approved automatically"
        else:
            return "rejected", None, None, "BNPL maximum limit is SGD 5,000"

    # No income data → send to underwriter
    if req.monthly_income is None:
        return "under_review", None, None, "Income verification required"

    # Debt-to-income check: monthly repayment / monthly income
    monthly_rate = INTEREST_RATES[req.loan_type] / 12
    if monthly_rate > 0:
        monthly_repayment = (
            req.requested_amount
            * monthly_rate
            * (1 + monthly_rate) ** req.term_months
            / ((1 + monthly_rate) ** req.term_months - 1)
        )
    else:
        monthly_repayment = req.requested_amount / req.term_months

    dti = monthly_repayment / req.monthly_income

    if dti > MAX_DTI:
        # Try a reduced amount that satisfies DTI
        if monthly_rate > 0:
            max_repayment = req.monthly_income * MAX_DTI
            reduced = (
                max_repayment
                * ((1 + monthly_rate) ** req.term_months - 1)
                / (monthly_rate * (1 + monthly_rate) ** req.term_months)
            )
        else:
            reduced = req.monthly_income * MAX_DTI * req.term_months
        reduced = round(reduced, 2)

        if reduced < 500:
            return "rejected", None, None, f"DTI ratio {dti:.2%} exceeds maximum {MAX_DTI:.0%}; minimum approvable amount not met"

        return (
            "approved",
            reduced,
            INTEREST_RATES[req.loan_type],
            f"Approved reduced amount: DTI {dti:.2%} exceeded max {MAX_DTI:.0%}",
        )

    return "approved", req.requested_amount, INTEREST_RATES[req.loan_type], "Credit assessment passed"
