from pydantic import BaseModel
from typing import Literal, Optional, Dict, Any
from datetime import datetime


class PaymentRequest(BaseModel):
    amount: float
    currency: str
    merchant_id: str
    customer_id: str
    payment_method: Literal["card", "bank_transfer", "ewallet"]
    metadata: Optional[Dict[str, Any]] = None


class PaymentResponse(BaseModel):
    id: str
    status: Literal["pending", "processing", "completed", "failed"]
    amount: float
    currency: str
    merchant_id: str
    customer_id: str
    created_at: datetime
    processed_at: Optional[datetime] = None
    transaction_fee: float
    risk_score: float


class PaymentStatus(BaseModel):
    id: str
    status: Literal["pending", "processing", "completed", "failed"]
    amount: float
    currency: str
    merchant_id: str
    customer_id: str
    created_at: datetime
    processed_at: Optional[datetime] = None
    transaction_fee: float
    risk_score: float
