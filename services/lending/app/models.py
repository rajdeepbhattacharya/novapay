from pydantic import BaseModel
from typing import Literal, Optional
from datetime import datetime


class LoanApplicationRequest(BaseModel):
    customer_id: str
    requested_amount: float
    loan_type: Literal["personal", "business", "bnpl"]
    term_months: int
    monthly_income: Optional[float] = None
    purpose: Optional[str] = None


class LoanApplicationResponse(BaseModel):
    id: str
    customer_id: str
    status: Literal["pending", "under_review", "approved", "rejected"]
    requested_amount: float
    approved_amount: Optional[float] = None
    interest_rate: Optional[float] = None
    term_months: int
    created_at: datetime
    decision_reason: Optional[str] = None
