"""Regression tests for answer accuracy: correct MSP figures and current season.

Run with: .venv/Scripts/python scripts/test_answer_accuracy.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.simulation.orchestrator import run_simulation

EXPECTED_MSP = {
    "wheat": 2585.0,        # 2026-27 Rabi, Government of India / CACP
    "rice_paddy": 2441.0,   # 2026-27 Kharif, common paddy
    "maize": 2410.0,        # 2026-27 Kharif
    "soybeans": 5708.0,     # 2026-27 Kharif, yellow soybean
}

failures = []
for crop, expected in EXPECTED_MSP.items():
    rec = run_simulation(crop, "india", 2026, 1000.0, "data")
    got = rec.msp_price_inr_per_quintal
    ok = abs(got - expected) < 0.01
    print(f"{'PASS' if ok else 'FAIL'} {crop}: MSP ₹{got:,.0f}/q (expected ₹{expected:,.0f})")
    if not ok:
        failures.append(f"{crop} MSP: got {got}, expected {expected}")

# Default year in the chat UI must be the current marketing season
ui_source = (ROOT / "chatbot_ui.py").read_text(encoding="utf-8")
if '"year": 2024' in ui_source:
    print("FAIL chatbot default year: 2024 (expected 2026)")
    failures.append("chatbot default year is 2024")
else:
    print("PASS chatbot default year is current season")

# --- Scale: the farmer's own area must drive volume, not the national harvest ---
small = run_simulation("wheat", "india", 2026, 2.0, "data")
large = run_simulation("wheat", "india", 2026, 200.0, "data")
print(f"INFO wheat 2 ha -> {small.available_volume_tonnes:,.0f} t; "
      f"200 ha -> {large.available_volume_tonnes:,.0f} t")
if small.available_volume_tonnes > 50:
    print(f"FAIL 2 ha produced {small.available_volume_tonnes:,.0f} t (national total, not farm-scale)")
    failures.append("farm size ignored: 2 ha produced national volume")
if large.available_volume_tonnes <= small.available_volume_tonnes * 20:
    print("FAIL volume does not scale with farm size")
    failures.append("volume does not scale with farm size")

# --- Price level: an Indian wheat estimate far above MSP is not credible ---
rec = run_simulation("wheat", "india", 2026, 100.0, "data")
msp_per_tonne = EXPECTED_MSP["wheat"] * 10
ratio = rec.expected_price_inr_per_tonne / msp_per_tonne
print(f"INFO wheat est. price ₹{rec.expected_price_inr_per_tonne:,.0f}/t = {ratio:.2f}x MSP/t")
if ratio > 1.5:
    print(f"FAIL estimated price {ratio:.2f}x MSP — implausible for Indian wheat")
    failures.append("price not anchored to MSP")

if failures:
    print(f"\n{len(failures)} FAILURE(S)")
    sys.exit(1)
print("\nAll accuracy checks passed")
