"""
NovaPay Demo Traffic Generator
Simulates realistic payment traffic for the Datadog demo.
Generates ~30-40 requests/minute across payments, fraud, and lending services.
"""
import os
import time
import random
import uuid
import logging

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

PAYMENTS_URL = os.environ.get("PAYMENTS_URL", "http://localhost:8001")
FRAUD_URL    = os.environ.get("FRAUD_URL",    "http://localhost:8003")
LENDING_URL  = os.environ.get("LENDING_URL",  "http://localhost:8002")

MERCHANTS = [
    "MERCHANT-LAZADA-001",
    "MERCHANT-GRAB-002",
    "MERCHANT-SHOPEE-003",
    "MERCHANT-GOJEK-004",
    "MERCHANT-SEA-005",
    "MERCHANT-TOKOPEDIA-006",
]
CURRENCIES      = ["SGD", "IDR", "MYR", "THB", "PHP", "USD"]
PAYMENT_METHODS = ["card", "bank_transfer", "ewallet"]

LOAN_TYPES  = ["personal", "business", "bnpl"]
TERM_MONTHS = [3, 6, 12, 24, 36]


def generate_payment() -> dict:
    """Build a realistic payment request with varied amounts."""
    amount_tier = random.choices(
        ["small", "medium", "high"],
        weights=[0.60, 0.30, 0.10],
    )[0]
    if amount_tier == "small":
        amount = random.uniform(10, 500)
    elif amount_tier == "medium":
        amount = random.uniform(500, 5000)
    else:
        amount = random.uniform(5000, 50000)   # triggers fraud signals

    return {
        "amount":         round(amount, 2),
        "currency":       random.choice(CURRENCIES),
        "merchant_id":    random.choice(MERCHANTS),
        "customer_id":    f"CUST-{uuid.uuid4().hex[:8]}",
        "payment_method": random.choice(PAYMENT_METHODS),
    }


def generate_fraud_request(payment: dict, transaction_id: str) -> dict:
    """Build a fraud analysis request from a payment."""
    req = {
        "transaction_id": transaction_id,
        "amount":         payment["amount"],
        "customer_id":    payment["customer_id"],
        "merchant_id":    payment["merchant_id"],
        "payment_method": payment["payment_method"],
    }
    # ~70% of requests include IP / device fingerprint
    if random.random() > 0.3:
        req["ip_address"] = f"203.0.{random.randint(1, 254)}.{random.randint(1, 254)}"
    if random.random() > 0.3:
        req["device_fingerprint"] = f"fp-{uuid.uuid4().hex[:12]}"
    return req


def generate_loan_request(customer_id: str) -> dict:
    """Build a loan application."""
    loan_type = random.choice(LOAN_TYPES)
    req = {
        "customer_id":      customer_id,
        "requested_amount": round(random.uniform(500, 50000), 2),
        "loan_type":        loan_type,
        "term_months":      random.choice(TERM_MONTHS),
        "purpose":          random.choice(["Home renovation", "Business expansion", "Education", "Travel", "Emergency"]),
    }
    if random.random() > 0.2:  # 80% provide income
        req["monthly_income"] = round(random.uniform(3000, 20000), 2)
    return req


def run():
    logger.info("NovaPay traffic generator starting...")
    logger.info(f"  Payments:  {PAYMENTS_URL}")
    logger.info(f"  Fraud:     {FRAUD_URL}")
    logger.info(f"  Lending:   {LENDING_URL}")

    # Wait for services to be ready
    for attempt in range(30):
        try:
            requests.get(f"{PAYMENTS_URL}/health", timeout=2)
            logger.info("Payments service ready.")
            break
        except Exception:
            logger.info(f"Waiting for payments service... ({attempt + 1}/30)")
            time.sleep(2)

    iteration = 0
    while True:
        iteration += 1
        try:
            # --- Payment flow ---
            payment_data = generate_payment()
            pay_resp = requests.post(
                f"{PAYMENTS_URL}/payments",
                json=payment_data,
                timeout=5,
            )
            if pay_resp.status_code == 201:
                payment = pay_resp.json()
                logger.info(
                    f"[{iteration}] Payment {payment['id']} | "
                    f"{payment['amount']:.2f} {payment['currency']} | "
                    f"{payment['payment_method']} | status={payment['status']} | "
                    f"risk={payment['risk_score']:.3f}"
                )
            else:
                logger.warning(f"Payment creation failed: {pay_resp.status_code} {pay_resp.text[:120]}")

            # --- Fraud analysis ---
            txn_id   = str(uuid.uuid4())
            fraud_req = generate_fraud_request(payment_data, txn_id)
            fraud_resp = requests.post(
                f"{FRAUD_URL}/fraud/analyze",
                json=fraud_req,
                timeout=5,
            )
            if fraud_resp.status_code == 200:
                result = fraud_resp.json()
                if result["risk_level"] in ("high", "critical"):
                    logger.warning(
                        f"[{iteration}] HIGH RISK {txn_id}: "
                        f"level={result['risk_level']} score={result['risk_score']:.3f} "
                        f"action={result['recommended_action']} signals={result['signals']}"
                    )
            else:
                logger.warning(f"Fraud analysis failed: {fraud_resp.status_code}")

            # --- Lending (~10% of iterations) ---
            if random.random() < 0.10:
                loan_req  = generate_loan_request(payment_data["customer_id"])
                loan_resp = requests.post(
                    f"{LENDING_URL}/loans",
                    json=loan_req,
                    timeout=5,
                )
                if loan_resp.status_code == 201:
                    loan = loan_resp.json()
                    logger.info(
                        f"[{iteration}] Loan {loan['id']} | "
                        f"{loan['loan_type']} {loan['requested_amount']:.2f} | "
                        f"status={loan['status']}"
                    )

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error (services may be starting): {e}")
        except requests.exceptions.Timeout:
            logger.error("Request timed out")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

        # ~30-40 requests/minute
        time.sleep(random.uniform(1.0, 2.5))


if __name__ == "__main__":
    run()
