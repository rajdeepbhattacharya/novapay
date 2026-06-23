import hashlib
from types import SimpleNamespace

from app import security_bug


def test_debug_payment_returns_subprocess_stdout(monkeypatch):
    captured = {}

    def fake_run(command, shell, capture_output, text):
        captured["command"] = command
        captured["shell"] = shell
        captured["capture_output"] = capture_output
        captured["text"] = text
        return SimpleNamespace(stdout="payment-log-line\n")

    monkeypatch.setattr(security_bug.subprocess, "run", fake_run)

    result = security_bug.debug_payment("PAY-123")

    assert result == "payment-log-line\n"
    assert captured["command"] == "grep PAY-123 /var/log/payments.log"
    assert captured["shell"] is True
    assert captured["capture_output"] is True
    assert captured["text"] is True


def test_hash_id_uses_md5_digest():
    customer_id = "cust_abc_42"

    assert (
        security_bug.hash_id(customer_id)
        == hashlib.md5(customer_id.encode()).hexdigest()
    )


def test_security_constants_are_available():
    assert security_bug.PAYMENT_GATEWAY_SECRET.startswith("sk_live_")
    assert security_bug.AWS_ACCESS_KEY.startswith("AKIA")
    assert security_bug.DB_ADMIN_PASSWORD.endswith("!")
