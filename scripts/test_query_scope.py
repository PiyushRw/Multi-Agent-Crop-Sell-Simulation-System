"""Regression tests: out-of-scope questions must be detected, not silently answered with a default crop.

Run with: .venv/Scripts/python scripts/test_query_scope.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from query_guard import detect_unsupported_commodity, SUPPORTED_CROPS

# The exact question from the bug report must be refused, not turned into a wheat answer.
CASES = {
    "transport cost of tea from assam to delhi": "tea",
    "Best market for coffee in Karnataka?": "coffee",
    "Should I store sugarcane or sell now?": "sugarcane",
    "MSP for cotton this year": "cotton",
    "price of mango in Delhi": "mango",
    "When should I sell wheat in Punjab?": None,
    "Best market for 500 ha rice in India?": None,
    "Should I store maize or sell now?": None,
    "Transport cost for wheat to Delhi?": None,
    "What's the MSP for wheat this year?": None,
    "sell my barley and sorghum": None,
}

failures = []
for query, expected in CASES.items():
    got = detect_unsupported_commodity(query)
    ok = got == expected
    print(f"{'PASS' if ok else 'FAIL'} {query!r} -> {got!r} (expected {expected!r})")
    if not ok:
        failures.append(f"{query!r}: got {got!r}, expected {expected!r}")

# Guard against the supported-crop list drifting from what the UI actually offers.
EXPECTED_SUPPORTED = {"wheat", "rice_paddy", "maize", "soybeans", "barley", "sorghum"}
if set(SUPPORTED_CROPS) != EXPECTED_SUPPORTED:
    print(f"FAIL supported crops differ: guard={set(SUPPORTED_CROPS)}, expected={EXPECTED_SUPPORTED}")
    failures.append("supported crop list out of sync")
else:
    print("PASS supported crop list in sync")

if failures:
    print(f"\n{len(failures)} FAILURE(S)")
    sys.exit(1)
print("\nAll query-scope checks passed")
