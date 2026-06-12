#!/bin/bash
# ============================================================
#  NovaPay Demo — Scenario Switch Script
#  APJ Royal Rumble 2026
#
#  Usage:
#    ./demo/apply_scenario.sh 1-fail   → Scenario 1: Coverage 8% (BLOCKS)
#    ./demo/apply_scenario.sh 1-fix    → Scenario 1: Coverage 96% (PASSES)
#    ./demo/apply_scenario.sh 2-gap    → Scenario 2: Show uncovered function
#    ./demo/apply_scenario.sh 2-fix    → Scenario 2: Add targeted tests
#    ./demo/apply_scenario.sh 3-fail   → Scenario 3: Security violations (BLOCKS)
#    ./demo/apply_scenario.sh 3-fix    → Scenario 3: Security fixed (PASSES)
#    ./demo/apply_scenario.sh reset    → Reset to clean main branch state
# ============================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
PAYMENTS_TESTS="$ROOT_DIR/services/payments/tests/test_payments.py"
PAYMENTS_MAIN="$ROOT_DIR/services/payments/app/main.py"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_bad()  { echo -e "${RED}[FAIL]${NC} $1"; }
log_good() { echo -e "${GREEN}[PASS]${NC} $1"; }
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }

case "$1" in

  # ──────────────────────────────────────────────────────────
  # SCENARIO 1-FAIL: Only 1 test, coverage ~8%
  # Shows: Quality Gate BLOCKING the deploy
  # ──────────────────────────────────────────────────────────
  1-fail)
    log_bad "Applying Scenario 1 — DEGRADED: 1 test, coverage ~8%"
    cp "$SCRIPT_DIR/scenario1_failing_tests.py" "$PAYMENTS_TESTS"
    cd "$ROOT_DIR"
    git add services/payments/tests/test_payments.py
    git commit -m "degraded: deleted all tests to hit sprint deadline (coverage 8%)"
    git push github degraded/rapid-development 2>/dev/null || \
    git push github main 2>/dev/null
    log_bad "Done. GitHub Actions will show Quality Gate BLOCKED at 8% coverage."
    echo ""
    echo "  Demo talking point:"
    echo "  'The team deleted tests to ship faster. Coverage collapsed to 8%.'"
    echo "  'Datadog's Quality Gate blocked the deploy automatically.'"
    ;;

  # ──────────────────────────────────────────────────────────
  # SCENARIO 1-FIX: Full test suite, coverage 96%
  # Shows: Quality Gate PASSING, deploy proceeds
  # ──────────────────────────────────────────────────────────
  1-fix)
    log_good "Applying Scenario 1 — FIXED: full tests, coverage ~96%"
    cp "$SCRIPT_DIR/scenario1_fixed_tests.py" "$PAYMENTS_TESTS"
    cd "$ROOT_DIR"
    git add services/payments/tests/test_payments.py
    git commit -m "fix: restore full test suite — coverage back to 96%"
    git push github main
    log_good "Done. Quality Gate will PASS. Deploy proceeds."
    echo ""
    echo "  Demo talking point:"
    echo "  'Tests restored. Coverage 96%. Quality Gate opens. Deploy flows.'"
    ;;

  # ──────────────────────────────────────────────────────────
  # SCENARIO 2-GAP: Show the uncovered function
  # Navigate to Datadog Code Coverage to show this
  # ──────────────────────────────────────────────────────────
  2-gap)
    log_info "Scenario 2 — GAP: showing uncovered function"
    echo ""
    echo "  No code change needed. Navigate in Datadog to:"
    echo ""
    echo "  Software Delivery → Test Optimization"
    echo "  → github.com/rajdeepbhattacharya/novapay"
    echo "  → Code Coverage tab"
    echo "  → Click app/main.py"
    echo "  → Highlight _calculate_risk_score() as uncovered"
    echo ""
    echo "  Talking point:"
    echo "  'This function processes $4.2M/day in fraud decisions.'"
    echo "  'Zero tests. Datadog shows exactly which lines are uncovered.'"
    echo "  'This is the function that caused the Black Friday outage.'"
    cat "$SCRIPT_DIR/scenario2_gap_highlight.py"
    ;;

  # ──────────────────────────────────────────────────────────
  # SCENARIO 2-FIX: Add targeted tests for the gap
  # Shows: Coverage closes, gap disappears in Datadog
  # ──────────────────────────────────────────────────────────
  2-fix)
    log_good "Applying Scenario 2 — FIX: adding targeted tests for risk_score gap"
    # Append the new tests to the existing test file
    cat "$SCRIPT_DIR/scenario2_new_tests.py" >> "$PAYMENTS_TESTS"
    cd "$ROOT_DIR"
    git add services/payments/tests/test_payments.py
    git commit -m "fix: add tests for _calculate_risk_score() — Black Friday regression prevention"
    git push github main
    log_good "Done. Coverage will increase. Gap closes in Datadog."
    echo ""
    echo "  Demo talking point:"
    echo "  'Datadog showed us the gap. We wrote 3 tests.'"
    echo "  'The IDR currency bug — the one that caused Black Friday — can never ship again.'"
    ;;

  # ──────────────────────────────────────────────────────────
  # SCENARIO 3-FAIL: Security vulnerabilities in main.py
  # Shows: PR Gate BLOCKING (secrets + SAST)
  # ──────────────────────────────────────────────────────────
  3-fail)
    log_bad "Applying Scenario 3 — FAILING: security violations in main.py"
    cp "$SCRIPT_DIR/scenario3_failing_main.py" "$PAYMENTS_MAIN"
    cd "$ROOT_DIR"
    git add services/payments/app/main.py
    git commit -m "feat: add payment debug utilities (CONTAINS SECURITY ISSUES)"
    git push github degraded/rapid-development
    log_bad "Done. Open a PR → watch Secret Scanning + SAST gates BLOCK it."
    echo ""
    echo "  PR Gates that will fire:"
    echo "  ❌ Secret Scanning: 5 CRITICAL secrets"
    echo "  ❌ SAST: subprocess shell=True (command injection)"
    echo "  ❌ SAST: MD5 hash (broken cryptography)"
    echo ""
    echo "  Demo talking point:"
    echo "  'NovaPay ships 40 times a day. Before Datadog, this code'"
    echo "  'would have reached production. 5 production secrets exposed.'"
    ;;

  # ──────────────────────────────────────────────────────────
  # SCENARIO 3-FIX: Secure version of main.py
  # Shows: All PR Gates PASSING
  # ──────────────────────────────────────────────────────────
  3-fix)
    log_good "Applying Scenario 3 — FIXED: all security issues resolved"
    cp "$SCRIPT_DIR/scenario3_fixed_main.py" "$PAYMENTS_MAIN"
    cd "$ROOT_DIR"
    git add services/payments/app/main.py
    git commit -m "fix: move secrets to env vars, fix command injection, use SHA-256"
    git push github main
    log_good "Done. All PR Gates will PASS."
    echo ""
    echo "  What changed:"
    echo "  ✅ Secrets → os.environ.get() (never in source code)"
    echo "  ✅ subprocess list args (no shell injection)"
    echo "  ✅ SHA-256 (replaces broken MD5)"
    echo "  ✅ IDR currency added (Black Friday fix)"
    echo ""
    echo "  Demo talking point:"
    echo "  'Datadog caught it before merge. 5 secrets. 2 vulnerabilities.'"
    echo "  'The fix: 3 lines changed. The gate opens.'"
    ;;

  # ──────────────────────────────────────────────────────────
  # RESET: Restore clean main branch
  # ──────────────────────────────────────────────────────────
  reset)
    log_info "Resetting to clean main branch state..."
    cd "$ROOT_DIR"
    git checkout main
    git pull github main 2>/dev/null || true
    log_good "Reset complete. On clean main branch."
    ;;

  *)
    echo "Usage: $0 {1-fail|1-fix|2-gap|2-fix|3-fail|3-fix|reset}"
    echo ""
    echo "  1-fail  → Coverage 8%  → Quality Gate BLOCKS"
    echo "  1-fix   → Coverage 96% → Quality Gate PASSES"
    echo "  2-gap   → Show uncovered _calculate_risk_score() in Datadog"
    echo "  2-fix   → Add 3 targeted tests → gap closes"
    echo "  3-fail  → 5 secrets + SAST violations → PR Gates BLOCK"
    echo "  3-fix   → All security fixed → PR Gates PASS"
    echo "  reset   → Back to clean main"
    exit 1
    ;;
esac
