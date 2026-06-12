"""
NovaPay Payments - SENSITIVE DATA IN LOGS
MAS Notice 626 compliance violation.
Customer PII and financial data logged in plain text.

Bits AI will detect:
  - Customer ID in logs (PDPA violation)
  - Payment amount in logs (financial data)
  - Gateway secret hardcoded (secret scanning)
"""
import logging
logger = logging.getLogger(__name__)

# ❌ COMPLIANCE VIOLATION — hardcoded secret
GATEWAY_SECRET = "sk_live_novapay_prod_4xK9mN2pL8qR"

# ❌ COMPLIANCE VIOLATION — PII in logs
def log_payment_bad(customer_id, amount, currency, card_last4):
    logger.info(f"Processing: customer={customer_id} amount={amount} "
                f"{currency} card=****{card_last4}")
    logger.info(f"Gateway auth: secret={GATEWAY_SECRET[:8]}...")  # still leaks!

# ✅ COMPLIANT — Bits AI fix
def log_payment_good(customer_id, amount, currency):
    masked_customer = f"CUST-***{customer_id[-4:]}"
    logger.info(f"Processing payment: customer={masked_customer} "
                f"currency={currency}")  # amount NOT logged
