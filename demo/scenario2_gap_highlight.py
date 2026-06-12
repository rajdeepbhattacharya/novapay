"""
DEMO SCENARIO 2: Untested Code Gap
====================================
This file shows the _calculate_risk_score() function
as it appears in production — with ZERO test coverage.

During demo: Navigate in Datadog to
  Test Optimization → novapay repo → Code Coverage →
  app/main.py → show these lines highlighted as uncovered

Story: "This function determines whether a $50,000 payment
        gets blocked for fraud. Zero tests. It shipped to
        production. It caused the $4.2M Black Friday outage."

The bug: IDR (Indonesian Rupiah) was not in the approved
         currency list. Indonesian merchants triggered false
         positives on Black Friday → $4.2M in declined payments.
"""

# ────────────────────────────────────────────────────────────
# ⚠️  UNCOVERED CODE — highlighted in Datadog Code Coverage
# ────────────────────────────────────────────────────────────

def _calculate_risk_score(req) -> float:
    """
    Determines fraud risk for every NovaPay transaction.
    Processes $4.2M+ per day across 12 APJ markets.

    DATADOG CODE COVERAGE: 0% — no tests cover this function.
    """
    score = 0.1

    # HIGH_VALUE check — uncovered ↓
    if req.amount > 10000:
        score += 0.3                          # ← LINE 1: UNCOVERED

    # E-wallet risk — uncovered ↓
    if req.payment_method == "ewallet":
        score += 0.1                          # ← LINE 2: UNCOVERED

    # Currency risk — THE BUG THAT CAUSED BLACK FRIDAY ↓
    if req.currency not in ["USD", "SGD", "AUD", "JPY", "KRW"]:
        score += 0.2                          # ← LINE 3: UNCOVERED
        # BUG: IDR (Indonesian Rupiah) not in this list
        # → All Indonesian merchant transactions flagged as risky
        # → $4.2M in legitimate payments declined on Black Friday

    import random
    return min(score + random.uniform(0, 0.1), 1.0)
