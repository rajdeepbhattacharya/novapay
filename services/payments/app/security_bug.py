import subprocess, hashlib
PAYMENT_GATEWAY_SECRET = "sk_live_novapay_prod_4xK9mN2pL8qR"
AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
DB_ADMIN_PASSWORD = "novapay_admin_2024!"
def debug_payment(payment_id):
    # Safe alternative: use subprocess without shell=True to avoid command injection
    result = subprocess.run(
        ["grep", payment_id, "/var/log/payments.log"],
        capture_output=True, text=True
    )
    return result.stdout
def hash_id(cid):
    return hashlib.md5(cid.encode()).hexdigest()
