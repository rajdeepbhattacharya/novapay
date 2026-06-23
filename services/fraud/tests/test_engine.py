import pytest
from app.engine import analyze_transaction
from app.models import FraudAnalysisRequest


def _make_request(**overrides):
    data = {
        "transaction_id": "TXN-ENGINE-001",
        "amount": 100.0,
        "customer_id": "CUST-123",
        "merchant_id": "MERCHANT-1",
        "payment_method": "card",
        "ip_address": "203.0.113.10",
        "device_fingerprint": "fp-123",
    }
    data.update(overrides)
    return FraudAnalysisRequest(**data)


@pytest.mark.parametrize(
    (
        "request_overrides",
        "noise",
        "expected_level",
        "expected_action",
        "expected_signals",
    ),
    [
        ({}, 0.0, "low", "allow", []),
        ({"amount": 6000.0}, 0.0, "medium", "review", ["HIGH_VALUE_TRANSACTION"]),
        (
            {"amount": 11000.0, "ip_address": None, "device_fingerprint": None},
            0.0,
            "high",
            "review",
            [
                "HIGH_VALUE_TRANSACTION",
                "VERY_HIGH_VALUE",
                "MISSING_IP_ADDRESS",
                "MISSING_DEVICE_FINGERPRINT",
            ],
        ),
        (
            {
                "amount": 11000.0,
                "ip_address": None,
                "device_fingerprint": None,
                "payment_method": "ewallet",
            },
            0.5,
            "critical",
            "block",
            [
                "HIGH_VALUE_TRANSACTION",
                "VERY_HIGH_VALUE",
                "MISSING_IP_ADDRESS",
                "MISSING_DEVICE_FINGERPRINT",
                "EWALLET_PAYMENT",
            ],
        ),
    ],
)
def test_analyze_transaction_risk_bands_and_signals(
    monkeypatch,
    request_overrides,
    noise,
    expected_level,
    expected_action,
    expected_signals,
):
    monkeypatch.setattr("app.engine.random.uniform", lambda _low, _high: noise)
    req = _make_request(**request_overrides)

    result = analyze_transaction(req)

    assert result.transaction_id == req.transaction_id
    assert result.risk_level == expected_level
    assert result.recommended_action == expected_action
    assert result.signals == expected_signals


def test_analyze_transaction_rounds_score_and_time(monkeypatch):
    monkeypatch.setattr("app.engine.random.uniform", lambda _low, _high: 0.0049)
    time_values = iter([100.0, 100.1234])
    monkeypatch.setattr("app.engine.time.time", lambda: next(time_values))
    req = _make_request(amount=6000.0)

    result = analyze_transaction(req)

    assert result.risk_score == 0.305
    assert result.analysis_time_ms == 123.4
