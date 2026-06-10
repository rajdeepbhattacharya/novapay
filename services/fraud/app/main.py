# CRITICAL: dd-trace auto-instrumentation must be imported FIRST
import ddtrace
ddtrace.patch_all()

from fastapi import FastAPI, HTTPException
from ddtrace import tracer
import logging
from typing import List
from collections import deque
from .models import FraudAnalysisRequest, FraudAnalysisResult
from .engine import analyze_transaction

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="NovaPay Fraud Detection Service", version="1.4.0")

# In-memory ring buffer of recent analysis results (last 100)
_recent_signals: deque = deque(maxlen=100)


@app.get("/health")
def health():
    return {"status": "healthy", "service": "fraud", "version": "1.4.0"}


@app.post("/fraud/analyze", response_model=FraudAnalysisResult)
def analyze(req: FraudAnalysisRequest):
    with tracer.trace("fraud.analyze", service="novapay-fraud", resource="analyze_transaction") as span:
        span.set_tag("fraud.transaction_id", req.transaction_id)
        span.set_tag("fraud.amount", req.amount)
        span.set_tag("fraud.payment_method", req.payment_method)
        span.set_tag("fraud.customer_id", req.customer_id)

        result = analyze_transaction(req)

        span.set_tag("fraud.risk_score", result.risk_score)
        span.set_tag("fraud.risk_level", result.risk_level)
        span.set_tag("fraud.action", result.recommended_action)
        span.set_tag("fraud.signal_count", len(result.signals))

        _recent_signals.append(result)

        if result.risk_level in ("high", "critical"):
            logger.warning(
                f"HIGH RISK transaction {req.transaction_id}: "
                f"score={result.risk_score} level={result.risk_level} "
                f"action={result.recommended_action} signals={result.signals}"
            )
        else:
            logger.info(
                f"Fraud analysis complete {req.transaction_id}: "
                f"score={result.risk_score} level={result.risk_level}"
            )

        return result


@app.get("/fraud/signals")
def get_signals():
    """Return the last 100 fraud analysis results."""
    return list(_recent_signals)


@app.get("/fraud/stats")
def fraud_stats():
    """Summary statistics over recent fraud analyses."""
    results = list(_recent_signals)
    if not results:
        return {
            "total_analyzed": 0,
            "by_risk_level": {},
            "by_action": {},
            "avg_risk_score": 0.0,
            "block_rate": 0.0,
        }

    by_level = {}
    by_action = {}
    total_score = 0.0

    for r in results:
        by_level[r.risk_level] = by_level.get(r.risk_level, 0) + 1
        by_action[r.recommended_action] = by_action.get(r.recommended_action, 0) + 1
        total_score += r.risk_score

    total = len(results)
    blocked = by_action.get("block", 0)

    return {
        "total_analyzed": total,
        "by_risk_level": by_level,
        "by_action": by_action,
        "avg_risk_score": round(total_score / total, 3),
        "block_rate": round(blocked / total, 3),
    }
