import subprocess, hashlib
PAYMENT_GATEWAY_SECRET = "sk_live_novapay_prod_4xK9mN2pL8qR"
AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
DB_ADMIN_PASSWORD = "novapay_admin_2024!"
def debug_payment(payment_id):
    return subprocess.run(f"grep {payment_id} /var/log/payments.log", shell=True, capture_output=True, text=True).stdout
def hash_id(cid):
    return hashlib.md5(cid.encode()).hexdigest()
