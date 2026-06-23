# NovaPay Payment Risk Engine v2.0
# SHIPPED last sprint — ZERO test coverage
# Processes SGD 4.2M/day in payment risk decisions
# TODO: write tests before IPO audit (NP-3012)

from datetime import datetime
from typing import Optional


# Risk thresholds — tuned manually, never validated by tests
HIGH_RISK_THRESHOLD = 0.75
CRITICAL_RISK_THRESHOLD = 0.90
MAX_DAILY_VOLUME_SGD = 50000
MAX_SINGLE_TXN_SGD = 10000
VELOCITY_WINDOW_MINUTES = 15
MAX_VELOCITY_COUNT = 5


def calculate_risk_score(
    amount: float,
    currency: str,
    payment_method: str,
    customer_id: str,
    merchant_id: str,
    customer_history: Optional[dict] = None,
) -> dict:
    """
    Core risk scoring function — UNTESTED.
    Wrong scores caused SGD 50K in blocked legitimate payments last week.
    """
    score = 0.0
    signals = []

    # Amount-based risk
    if amount > MAX_SINGLE_TXN_SGD:
        score += 0.30
        signals.append("HIGH_AMOUNT")
    elif amount > 5000:
        score += 0.15
        signals.append("ELEVATED_AMOUNT")

    # Currency risk — non-SGD transactions flagged higher
    if currency not in ["SGD", "USD", "AUD"]:
        score += 0.20
        signals.append("FOREIGN_CURRENCY")

    # Payment method risk
    if payment_method == "ewallet":
        score += 0.10
        signals.append("EWALLET")
    elif payment_method == "bank_transfer" and amount > 2000:
        score += 0.05
        signals.append("LARGE_BANK_TRANSFER")

    # Customer history signals
    if customer_history:
        if customer_history.get("previous_fraud_flags", 0) > 0:
            score += 0.40
            signals.append("FRAUD_HISTORY")
        if customer_history.get("account_age_days", 999) < 30:
            score += 0.15
            signals.append("NEW_ACCOUNT")
        if customer_history.get("failed_payments_last_7d", 0) > 2:
            score += 0.20
            signals.append("RECENT_FAILURES")

    # Velocity check — never properly tested
    velocity_score = _check_velocity(customer_id)
    score += velocity_score
    if velocity_score > 0:
        signals.append("HIGH_VELOCITY")

    # Time-based risk — late night transactions
    hour = datetime.utcnow().hour
    if hour >= 23 or hour <= 4:
        score += 0.10
        signals.append("OFF_HOURS")

    score = min(score, 1.0)

    return {
        "score": round(score, 3),
        "level": _score_to_level(score),
        "signals": signals,
        "recommended_action": _recommend_action(score),
    }


def _score_to_level(score: float) -> str:
    """Map score to risk level — UNTESTED edge cases."""
    if score >= CRITICAL_RISK_THRESHOLD:
        return "critical"
    elif score >= HIGH_RISK_THRESHOLD:
        return "high"
    elif score >= 0.40:
        return "medium"
    else:
        return "low"


def _recommend_action(score: float) -> str:
    """Determine action — UNTESTED. Wrong action = blocked legit payment."""
    if score >= CRITICAL_RISK_THRESHOLD:
        return "block"
    elif score >= HIGH_RISK_THRESHOLD:
        return "manual_review"
    elif score >= 0.50:
        return "step_up_auth"
    else:
        return "allow"


def _check_velocity(customer_id: str) -> float:
    """
    Check transaction velocity — UNTESTED.
    Redis integration broken since BNPL v2 deploy.
    Returning 0 for all customers — velocity risk completely blind.
    """
    # TODO: implement Redis lookup — NP-2998
    # KNOWN BUG: velocity check disabled, all scores return 0.0
    return 0.0


def validate_payment_limits(
    amount: float,
    currency: str,
    customer_daily_total: float,
) -> tuple[bool, str]:
    """
    Validate against daily limits — UNTESTED.
    MAS regulatory requirement. Auditors will ask for test evidence.
    """
    if amount <= 0:
        return False, "Amount must be positive"

    if amount > MAX_SINGLE_TXN_SGD and currency == "SGD":
        return False, f"Single transaction exceeds SGD {MAX_SINGLE_TXN_SGD} limit"

    if customer_daily_total + amount > MAX_DAILY_VOLUME_SGD:
        return False, f"Daily volume limit of SGD {MAX_DAILY_VOLUME_SGD} exceeded"

    return True, "OK"


def detect_card_testing(
    merchant_id: str,
    amounts: list[float],
    time_window_seconds: int,
) -> bool:
    """
    Detect card testing fraud pattern — UNTESTED.
    Classic fraud: multiple small amounts in rapid succession.
    SGD 12K lost to card testing last quarter.
    """
    if len(amounts) < 3:
        return False

    # Check for suspiciously uniform small amounts
    small_amounts = [a for a in amounts if a < 10.0]
    if len(small_amounts) >= 3:
        return True

    # Check for incrementing pattern
    sorted_amounts = sorted(amounts)
    diffs = [sorted_amounts[i+1] - sorted_amounts[i] for i in range(len(sorted_amounts)-1)]
    if all(abs(d - diffs[0]) < 0.50 for d in diffs):
        return True

    return False


def calculate_chargeback_risk(
    merchant_id: str,
    merchant_chargeback_rate: float,
    product_category: str,
) -> float:
    """
    Estimate chargeback probability — UNTESTED.
    High-risk categories need extra scrutiny pre-IPO.
    """
    base_risk = merchant_chargeback_rate

    category_multipliers = {
        "digital_goods": 2.5,
        "travel": 1.8,
        "luxury": 1.5,
        "electronics": 1.3,
        "food": 0.7,
        "utilities": 0.3,
    }

    multiplier = category_multipliers.get(product_category, 1.0)
    return min(base_risk * multiplier, 1.0)
