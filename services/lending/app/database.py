import uuid
from threading import Lock
from typing import Dict
from .models import LoanApplicationResponse

# In-memory store for loan applications
loans_db: Dict[str, LoanApplicationResponse] = {}
_db_lock = Lock()


def generate_loan_id() -> str:
    """Generate a unique loan ID in the format LOAN-XXXXXXXX."""
    return f"LOAN-{uuid.uuid4().hex[:8].upper()}"
