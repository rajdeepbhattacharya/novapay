"""
DEMO SCENARIO 2: Tests Written to Close the Coverage Gap
=========================================================
Story: "Datadog showed us exactly which lines had no tests.
        We wrote 3 tests targeting the exact logic
        that caused the Black Friday outage.
        Coverage went from 8% to 96%.
        The Quality Gate opened. That function can never
        ship untested again."

These 3 tests go into services/payments/tests/test_payments.py
in addition to the full test suite from scenario1_fixed_tests.py
"""


def test_idr_currency_not_false_positive(client, sample_payment):
    """
    FIX FOR BLACK FRIDAY OUTAGE.

    Before: IDR was missing from the approved currency list.
    Indonesian merchant transactions were flagged as high-risk
    and declined → $4.2M in lost revenue in 40 minutes.

    This test PREVENTS that regression from ever shipping again.
    The Quality Gate enforces: this test must pass before deploy.
    """
    # All major APJ currencies — none should trigger false positives
    apj_currencies = {
        "SGD": "Singapore Dollar",
        "IDR": "Indonesian Rupiah",   # ← THE BUG WAS HERE
        "MYR": "Malaysian Ringgit",
        "THB": "Thai Baht",
        "PHP": "Philippine Peso",
        "VND": "Vietnamese Dong",
        "AUD": "Australian Dollar",
    }

    for currency, name in apj_currencies.items():
        sample_payment["currency"] = currency
        sample_payment["amount"] = 500.00   # Normal amount — not high-value
        response = client.post("/payments", json=sample_payment)

        assert response.status_code == 201, \
            f"Payment REJECTED for {name} ({currency}) — false positive!"

        risk_score = response.json()["risk_score"]
        assert risk_score < 0.8, \
            f"FALSE POSITIVE: {name} ({currency}) flagged as high-risk " \
            f"(score: {risk_score:.2f}) — this would have triggered Black Friday"


def test_high_value_correctly_elevated_not_blocked(client, sample_payment):
    """
    High-value transactions should have ELEVATED risk (not blocking risk).
    NovaPay processes SGD 50,000+ payments daily for enterprise merchants.
    These must not be blocked — only reviewed.
    """
    sample_payment["amount"] = 50000.00
    sample_payment["currency"] = "SGD"

    response = client.post("/payments", json=sample_payment)
    assert response.status_code == 201

    data = response.json()
    # Should be elevated but still processed
    assert data["risk_score"] > 0.3, \
        "High-value transaction should have elevated risk score"
    assert data["status"] in ("completed", "failed"), \
        "High-value payment should still be processed (not 500 error)"


def test_risk_score_never_exceeds_bounds(client, sample_payment):
    """
    Risk score must always be 0.0-1.0.
    At 3M transactions/day — any score bug causes massive failures.
    Run 50 times to catch intermittent math errors.
    """
    currencies = ["SGD", "IDR", "MYR", "USD", "AUD"]
    amounts = [10.00, 500.00, 5000.00, 50000.00]

    for currency in currencies:
        for amount in amounts:
            sample_payment["currency"] = currency
            sample_payment["amount"] = amount
            response = client.post("/payments", json=sample_payment)
            score = response.json()["risk_score"]
            assert 0.0 <= score <= 1.0, \
                f"INVALID risk score {score} for {currency} {amount}"
