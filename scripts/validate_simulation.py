# Validation script for simulation outputs
import sys
import os

# Get project root (parent of scripts directory)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.simulation.orchestrator import run_simulation
from src.agents.models import CropType, Country, MarketRegion

def test_wheat_usa():
    rec = run_simulation('wheat', 'usa', 2024, 1000.0, 'data')
    assert rec.crop.value == 'wheat'
    assert rec.country.value == 'usa'
    assert 1 <= rec.recommended_sell_month <= 12
    assert rec.confidence_score > 0
    assert rec.net_profit_usd > 0
    print('PASS: wheat/usa')

def test_maize_brazil():
    rec = run_simulation('maize', 'brazil', 2024, 1000.0, 'data')
    assert rec.crop.value == 'maize'
    assert rec.country.value == 'brazil'
    assert 1 <= rec.recommended_sell_month <= 12
    print('PASS: maize/brazil')

def test_soybeans_argentina():
    rec = run_simulation('soybeans', 'argentina', 2024, 1000.0, 'data')
    assert rec.crop.value == 'soybeans'
    assert rec.country.value == 'argentina'
    print('PASS: soybeans/argentina')

def test_rice_india():
    rec = run_simulation('rice_paddy', 'india', 2024, 1000.0, 'data')
    assert rec.crop.value == 'rice_paddy'
    assert rec.country.value == 'india'
    assert 1 <= rec.recommended_sell_month <= 12
    print('PASS: rice/india')

def test_structure():
    """Verify SellRecommendation has all expected fields."""
    rec = run_simulation('wheat', 'usa', 2024, 1000.0, 'data')
    required = ['crop', 'country', 'production_year', 'available_volume_tonnes',
                'recommended_sell_month', 'recommended_market', 'expected_price_usd_per_tonne',
                'logistics_cost', 'net_price_usd_per_tonne', 'total_revenue_usd',
                'total_cost_usd', 'net_profit_usd', 'confidence_score',
                'risk_factors', 'farmer_reasoning', 'market_reasoning',
                'logistics_reasoning', 'consensus_reasoning', 'alternatives']
    for field in required:
        assert hasattr(rec, field), f'Missing field: {field}'
    print('PASS: structure validation')

if __name__ == '__main__':
    test_wheat_usa()
    test_maize_brazil()
    test_soybeans_argentina()
    test_rice_india()
    test_structure()
    print('All validation tests passed!')