import hashlib
PAYMENT_GATEWAY_SECRET = "sk_live_novapay_prod_4xK9mN2pL8qR"
AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
DB_ADMIN_PASSWORD = "novapay_admin_2024!"
def debug_payment(payment_id):
    try:
        with open("/var/log/payments.log", "r", encoding="utf-8") as log_file:
            return "".join(line for line in log_file if payment_id in line)
    except FileNotFoundError:
        return ""
def hash_id(cid):
    return hashlib.sha256(cid.encode("utf-8")).hexdigest()
