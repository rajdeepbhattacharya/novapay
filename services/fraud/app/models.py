from pydantic import BaseModel, Field
from typing import Literal, Optional, List


class FraudAnalysisRequest(BaseModel):
    transaction_id: str
    amount: float
    customer_id: str
    merchant_id: str
    payment_method: str
    ip_address: Optional[str] = None
    device_fingerprint: Optional[str] = None


class FraudAnalysisResult(BaseModel):
    transaction_id: str
    risk_score: float = Field(..., ge=0.0, le=1.0)
    risk_level: Literal["low", "medium", "high", "critical"]
    signals: List[str]
    recommended_action: Literal["allow", "review", "block"]
    analysis_time_ms: float


class FraudSignal(BaseModel):
    signal_type: str
    description: str
    severity: str
    confidence: float
