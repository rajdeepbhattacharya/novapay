"""
NovaPay Payments - MISSING INPUT VALIDATION
This file demonstrates the security issue Bits AI will detect and fix.
The create_payment endpoint accepts:
  - Negative amounts (reverses money flow)
  - Empty merchant IDs
  - Unsupported currencies

Example exploit:
  POST /payments {"amount": -50000, "currency": "FAKE", "merchant_id": ""}
  Result: negative transaction fee returned, funds flow backwards
"""

# ❌ VULNERABLE endpoint (no validation)
def create_payment_vulnerable(req):
    fee = round(req.amount * 0.015, 2)   # negative if amount < 0!
    return {"fee": fee, "status": "processed"}

# ✅ SECURE endpoint (Bits AI will suggest this fix)
def create_payment_secure(req):
    VALID_CURRENCIES = {"SGD", "USD", "AUD", "IDR", "MYR", "THB", "PHP"}
    if req.amount <= 0:
        raise ValueError("Amount must be positive")
    if not req.merchant_id:
        raise ValueError("Merchant ID required")
    if req.currency not in VALID_CURRENCIES:
        raise ValueError(f"Currency {req.currency} not supported")
    fee = round(req.amount * 0.015, 2)
    return {"fee": fee, "status": "processed"}
