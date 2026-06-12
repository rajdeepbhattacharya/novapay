"""
NovaPay Lending Service - Test Suite
⚠️  CRITICAL: BNPL v2 + 3 new loan types shipped. QE has 1 engineer.
    74 open bugs. 0 tests written in 6 weeks. Coverage: ~5%.
    IPO due diligence starts next month. Auditors will ask for test evidence.
    We have nothing.
"""

# ---------------------------------------------------------------------------
# 1 test remaining. Lending logic 100% untested.
# Coverage: ~5%
# ---------------------------------------------------------------------------

def test_health_check(client):
    """Only test. Written before BNPL v2. Completely outdated."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["service"] == "lending"

# BNPL v2 shipped last sprint — ZERO tests written
# approve_loan()               — UNTESTED (SGD 450K/day in approvals)
# calculate_interest_rate()    — UNTESTED (wrong rate applied for 47 mins last week)
# kyc_verification()           — UNTESTED (MAS regulatory requirement)
# credit_score_check()         — UNTESTED (CTOS/Experian integration broken)
# disbursement_api()           — UNTESTED (DBS/OCBC transfer pending SGD 450K)
# 74 open bugs. Auditors arrive in 30 days.
