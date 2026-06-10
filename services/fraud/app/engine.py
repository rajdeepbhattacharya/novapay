import time
import random
from .models import FraudAnalysisRequest, FraudAnalysisResult

FRAUD_RULES = [
    {"name": "high_value_transaction", "threshold": 5000, "score": 0.25},
    {"name": "unusual_merchant", "merchants": ["MERCHANT-UNKNOWN"], "score": 0.3},
    {"name": "velocity_check", "score": 0.15},  # Simplified
]


def analyze_transaction(req: FraudAnalysisRequest) -> FraudAnalysisResult:
    start = time.time()
    signals = []
    score = 0.05  # base score

    if req.amount > 5000:
        signals.append("HIGH_VALUE_TRANSACTION")
        score += 0.25
    if req.amount > 10000:
        signals.append("VERY_HIGH_VALUE")
        score += 0.15
    if not req.ip_address:
        signals.append("MISSING_IP_ADDRESS")
        score += 0.1
    if not req.device_fingerprint:
        signals.append("MISSING_DEVICE_FINGERPRINT")
        score += 0.1
    if req.payment_method == "ewallet":
        signals.append("EWALLET_PAYMENT")
        score += 0.05

    # Add some noise
    score = min(score + random.uniform(0, 0.05), 1.0)

    if score < 0.3:
        risk_level = "low"
        action = "allow"
    elif score < 0.6:
        risk_level = "medium"
        action = "review"
    elif score < 0.8:
        risk_level = "high"
        action = "review"
    else:
        risk_level = "critical"
        action = "block"

    return FraudAnalysisResult(
        transaction_id=req.transaction_id,
        risk_score=round(score, 3),
        risk_level=risk_level,
        signals=signals,
        recommended_action=action,
        analysis_time_ms=round((time.time() - start) * 1000, 2),
    )
