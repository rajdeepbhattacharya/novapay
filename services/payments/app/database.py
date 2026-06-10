import uuid
from threading import Lock
from typing import Dict
from .models import PaymentResponse

# In-memory store for payments
payments_db: Dict[str, PaymentResponse] = {}
_db_lock = Lock()


def generate_payment_id() -> str:
    """Generate a unique payment ID in the format PAY-XXXXXXXX."""
    return f"PAY-{uuid.uuid4().hex[:8].upper()}"
