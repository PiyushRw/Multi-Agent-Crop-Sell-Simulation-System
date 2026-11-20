#!/usr/bin/env python
"""
Crop Sell Simulation - Demo Script

This script demonstrates the multi-agent crop selling optimization system
with three cooperating agents (Farmer, Market, Logistics) using real FAOSTAT data.
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.simulation.orchestrator import run_simulation, SimulationConfig
from src.agents.models import CropType, Country, MarketRegion


def run_demo():
    """Run the demo simulation for multiple crop/country combinations."""
    
    # Demo scenarios - India-focused
    scenarios = [
        {
            "crop": "wheat",
            "country": "india",
            "year": 2024,
            "farm_size": 1000.0,
            "description": "Wheat in India (Major Rabi Crop, Northern States)"
        },
        {
            "crop": "rice_paddy",
            "country": "india",
            "year": 2024,
            "farm_size": 1000.0,
            "description": "Rice in India (Major Kharif Crop, Eastern & Southern States)"
        },
        {
            "crop": "maize",
            "country": "india",
            "year": 2024,
            "farm_size": 1000.0,
            "description": "Maize in India (Growing Kharif & Rabi Crop)"
        },
    ]
    
    print("=" * 80)
    print("MULTI-AGENT CROP SELL SIMULATION - DEMONSTRATION")
    print("=" * 80)
    print("Agents: Farmer (production) + Market (prices) + Logistics (transport)")
    print("Data Source: FAOSTAT (Production, Producer Prices, Value of Production)")
    print("=" * 80)
    print()
    
    results = []
    
    for scenario in scenarios:
        print(f"\n{'='*80}")
        print(f"SCENARIO: {scenario['description']}")
        print(f"{'='*80}")
        
        try:
            rec = run_simulation(
                crop=scenario["crop"],
                country=scenario["country"],
                year=scenario["year"],
                farm_size=scenario["farm_size"],
                data_dir="data"
            )
            
            # Print formatted recommendation
            print_recommendation(rec)
            
            # Store for summary
            results.append({
                "scenario": scenario["description"],
                "recommendation": rec.to_dict() if hasattr(rec, 'to_dict') else serialize_recommendation(rec)
            })
            
        except Exception as e:
            print(f"Error running scenario {scenario['crop']}/{scenario['country']}: {e}")
            import traceback
            traceback.print_exc()
    
    # Print summary table
    print_summary(results)
    
    # Save detailed results
    save_results(results)
    
    return results


def print_recommendation(rec):
    """Print a formatted sell recommendation."""

    print("\n📋 SELL RECOMMENDATION")
    print("-" * 50)
    print(f"  Crop:              {rec.crop.value.title()}")
    print(f"  Country:           {rec.country.value.title()}")
    print(f"  Production Year:   {rec.production_year}")
    print(f"  Available Volume:  {rec.available_volume_tonnes:,.0f} tonnes")
    print()

    # Display INR for India, USD for others
    is_india = rec.country.value.lower() == "india"
    currency = "₹" if is_india else "$"
    price_per_t = rec.expected_price_inr_per_tonne if is_india else rec.expected_price_usd_per_tonne
    logistics_per_t = rec.logistics_cost_inr_per_tonne if is_india else rec.logistics_cost.total_cost_usd_per_tonne
    net_per_t = rec.net_price_inr_per_tonne if is_india else rec.net_price_usd_per_tonne
    total_rev = rec.total_revenue_inr if is_india else rec.total_revenue_usd
    total_cost = rec.total_cost_inr if is_india else rec.total_cost_usd
    net_profit = rec.net_profit_inr if is_india else rec.net_profit_usd

    print(f"  📅 Recommended Sell Month:  {rec.recommended_sell_month} ({month_name(rec.recommended_sell_month)})")
    print(f"  🏪 Recommended Market:      {rec.recommended_market.value.replace('_', ' ').title()}")
    print(f"  {currency} Expected Price:          {currency}{price_per_t:,.2f}/tonne")
    print(f"  {currency} Logistics Cost:          {currency}{logistics_per_t:,.2f}/tonne")
    print(f"  {currency} Net Price:               {currency}{net_per_t:,.2f}/tonne")
    print()
    print(f"  {currency} Total Revenue:           {currency}{total_rev:,.0f}")
    print(f"  {currency} Total Cost:              {currency}{total_cost:,.0f}")
    print(f"  {currency} Net after transport:     {currency}{net_profit:,.0f} (excl. production cost)")
    print(f"  🎯 Confidence Score:        {rec.confidence_score:.0%}")
    print()
    
    # Logistics breakdown
    if rec.logistics_cost:
        print("  🚚 LOGISTICS BREAKDOWN")
        # Handle both enum and string for transport_mode
        tm = rec.logistics_cost.transport_mode
        tm_str = tm.value.replace('_', ' ').title() if hasattr(tm, 'value') else str(tm).replace('_', ' ').title()
        print(f"    Transport Mode:   {tm_str}")
        print(f"    Distance:         {rec.logistics_cost.distance_km:,.0f} km")
        if is_india:
            print(f"    Transport Cost:   ₹{rec.logistics_breakdown.get('transport_inr', 0):,.2f}/tonne")
            print(f"    Storage Cost:     ₹{rec.logistics_breakdown.get('storage_inr', 0):,.2f}/tonne")
            print(f"    Handling Cost:    ₹{rec.logistics_breakdown.get('handling_inr', 0):,.2f}/tonne")
            print(f"    Insurance Cost:   ₹{rec.logistics_breakdown.get('insurance_inr', 0):,.2f}/tonne")
        else:
            print(f"    Transport Cost:   ${rec.logistics_cost.transport_cost_usd_per_tonne:,.2f}/tonne")
            print(f"    Storage Cost:     ${rec.logistics_cost.storage_cost_usd_per_tonne_per_month:,.2f}/tonne/month")
            print(f"    Handling Cost:    ${rec.logistics_cost.handling_cost_usd_per_tonne:,.2f}/tonne")
            print(f"    Insurance Cost:   ${rec.logistics_cost.insurance_cost_usd_per_tonne:,.2f}/tonne")
        print(f"    Transit Time:     {rec.logistics_cost.transit_time_days} days")
        print()
    
    # Agent reasoning
    print("  🧠 AGENT REASONING")
    print(f"    👨‍🌾 Farmer:  {rec.farmer_reasoning[:150]}...")
    print(f"    📈 Market:  {rec.market_reasoning[:150]}...")
    print(f"    🚛 Logistics: {rec.logistics_reasoning[:150]}...")
    print()
    
    # Risk factors
    if rec.risk_factors:
        print("  ⚠️  RISK FACTORS")
        for risk in rec.risk_factors:
            print(f"    - {risk}")
        print()
    
    # Alternatives
    if rec.alternatives:
        print("  🔄 ALTERNATIVE OPTIONS")
        for alt in rec.alternatives[:3]:
            if is_india:
                net_val = alt.get('net_price_inr', alt.get('net_price_usd', alt.get('net_price', 0)) * 93.5)
                print(f"    Month {alt['month']:2d} ({month_name(alt['month'])}): "
                      f"₹{net_val:,.2f}/t net - {alt['reason']}")
            else:
                net_val = alt.get('net_price_usd', alt.get('net_price', 0))
                print(f"    Month {alt['month']:2d} ({month_name(alt['month'])}): "
                      f"${net_val:,.2f}/t net - {alt['reason']}")
        print()


def month_name(month: int) -> str:
    """Get month name from number."""
    months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return months[month] if 1 <= month <= 12 else "N/A"


def serialize_recommendation(rec):
    """Serialize recommendation to dict."""
    is_india = rec.country.value.lower() == "india"
    return {
        "crop": rec.crop.value,
        "country": rec.country.value,
        "production_year": rec.production_year,
        "available_volume_tonnes": rec.available_volume_tonnes,
        "recommended_sell_month": rec.recommended_sell_month,
        "recommended_market": rec.recommended_market.value,
        "expected_price_usd_per_tonne": rec.expected_price_usd_per_tonne,
        "expected_price_inr_per_tonne": rec.expected_price_inr_per_tonne if is_india else 0,
        "logistics_cost_usd_per_tonne": rec.logistics_cost.total_cost_usd_per_tonne if rec.logistics_cost else 0,
        "logistics_cost_inr_per_tonne": rec.logistics_cost_inr_per_tonne if is_india else 0,
        "net_price_usd_per_tonne": rec.net_price_usd_per_tonne,
        "net_price_inr_per_tonne": rec.net_price_inr_per_tonne if is_india else 0,
        "total_revenue_usd": rec.total_revenue_usd,
        "total_revenue_inr": rec.total_revenue_inr if is_india else 0,
        "total_cost_usd": rec.total_cost_usd,
        "total_cost_inr": rec.total_cost_inr if is_india else 0,
        "net_profit_usd": rec.net_profit_usd,
        "net_profit_inr": rec.net_profit_inr if is_india else 0,
        "confidence_score": rec.confidence_score,
        "risk_factors": rec.risk_factors,
        "farmer_reasoning": rec.farmer_reasoning,
        "market_reasoning": rec.market_reasoning,
        "logistics_reasoning": rec.logistics_reasoning,
        "consensus_reasoning": rec.consensus_reasoning,
        "alternatives": rec.alternatives
    }


def print_summary(results):
    """Print a summary table of all scenarios."""
    print("\n" + "=" * 80)
    print("SUMMARY TABLE")
    print("=" * 80)
    print(f"{'Scenario':<35} {'Month':>5} {'Market':<20} {'Price/t':>12} {'Net/t':>12} {'Net/transport':>18} {'Conf':>6}")
    print("-" * 110)
    
    for r in results:
        rec = r["recommendation"]
        scenario = r["scenario"][:34]
        month = month_name(rec.get("recommended_sell_month", 0))
        market = rec.get("recommended_market", "N/A")[:19]
        is_india = "india" in r["scenario"].lower()
        
        if is_india:
            price = f"₹{rec.get('expected_price_inr_per_tonne', 0):,.0f}"
            net = f"₹{rec.get('net_price_inr_per_tonne', 0):,.0f}"
            profit = f"₹{rec.get('net_profit_inr', 0):,.0f}"
        else:
            price = f"${rec.get('expected_price_usd_per_tonne', 0):,.0f}"
            net = f"${rec.get('net_price_usd_per_tonne', 0):,.0f}"
            profit = f"${rec.get('net_profit_usd', 0):,.0f}"
        conf = f"{rec.get('confidence_score', 0)*100:.0f}%"
        
        print(f"{scenario:<35} {month:>5} {market:<20} {price:>12} {net:>12} {profit:>18} {conf:>6}")


def save_results(results):
    """Save detailed results to JSON file."""
    output_file = Path("demo_results.json")
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n📄 Detailed results saved to: {output_file}")


if __name__ == "__main__":
    run_demo()