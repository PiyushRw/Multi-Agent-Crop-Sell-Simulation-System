"""
Core data models for the multi-agent crop sell simulation.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime
import uuid


class CropType(Enum):
    WHEAT = "wheat"
    MAIZE = "maize"
    RICE = "rice_paddy"
    SOYBEANS = "soybeans"
    BARLEY = "barley"
    SORGHUM = "sorghum"


class Country(Enum):
    USA = "usa"
    BRAZIL = "brazil"
    INDIA = "india"
    CHINA = "china"
    ARGENTINA = "argentina"
    RUSSIA = "russia"
    UKRAINE = "ukraine"
    CANADA = "canada"
    AUSTRALIA = "australia"
    FRANCE = "france"
    GERMANY = "germany"


class MarketRegion(Enum):
    DOMESTIC = "domestic"
    EXPORT_NORTH_AMERICA = "export_north_america"
    EXPORT_SOUTH_AMERICA = "export_south_america"
    EXPORT_EUROPE = "export_europe"
    EXPORT_ASIA = "export_asia"
    EXPORT_AFRICA = "export_africa"
    EXPORT_MIDDLE_EAST = "export_middle_east"


class TransportMode(Enum):
    TRUCK = "truck"
    RAIL = "rail"
    BARGE = "barge"
    OCEAN_VESSEL = "ocean_vessel"
    CONTAINER = "container"


# Official Minimum Support Prices for India, marketing season 2026-27 (₹/quintal).
# Source: Government of India / CACP, updated 30 Sep 2026. Single source of truth —
# all agents read this so MSP figures cannot drift apart.
INDIA_MSP_2026_27 = {
    CropType.WHEAT: 2585.0,     # Rabi 2026-27
    CropType.RICE: 2441.0,      # Kharif 2026-27, common paddy (Grade A: 2461)
    CropType.MAIZE: 2410.0,     # Kharif 2026-27
    CropType.SOYBEANS: 5708.0,  # Kharif 2026-27, yellow soybean
}
MSP_SEASON = "2026-27"
MSP_SOURCE = "Government of India / CACP"
# Approximate USD/INR rate, Nov 2026 (used only for display conversion).
USD_TO_INR = 93.5
CROP_CODE_TO_CROP = {15: CropType.WHEAT, 27: CropType.RICE,
                     56: CropType.MAIZE, 236: CropType.SOYBEANS}


@dataclass
class PricePoint:
    """A single price observation."""
    year: int
    month: Optional[int] = None  # None = annual
    price_usd_per_tonne: float = 0.0
    price_lcu_per_tonne: float = 0.0
    price_index: float = 100.0  # 2014-2016 = 100
    source: str = "FAOSTAT"


@dataclass
class ProductionData:
    """Production statistics for a crop/country/year."""
    country: Country
    crop: CropType
    year: int
    area_harvested_ha: float = 0.0
    production_tonnes: float = 0.0
    yield_kg_per_ha: float = 0.0
    value_usd_thousand: float = 0.0


@dataclass
class HarvestCalendar:
    """Harvest timing for a crop in a country."""
    crop: CropType
    country: Country
    planting_months: List[int] = field(default_factory=list)
    harvest_start_month: int = 1
    harvest_peak_months: List[int] = field(default_factory=list)
    harvest_end_month: int = 12


@dataclass
class LogisticsCost:
    """Transport and storage cost breakdown."""
    origin_country: Country
    destination_region: MarketRegion
    transport_mode: Any  # TransportMode enum or string
    distance_km: float
    transport_cost_usd_per_tonne: float
    storage_cost_usd_per_tonne_per_month: float
    handling_cost_usd_per_tonne: float
    insurance_cost_usd_per_tonne: float
    transit_time_days: int
    total_cost_usd_per_tonne: float


@dataclass
class SellRecommendation:
    """A complete sell recommendation from the multi-agent system."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Context
    crop: CropType = CropType.WHEAT
    country: Country = Country.INDIA
    production_year: int = 2024
    available_volume_tonnes: float = 0.0
    
    # Recommendation
    recommended_sell_month: int = 1
    recommended_market: MarketRegion = MarketRegion.DOMESTIC
    expected_price_usd_per_tonne: float = 0.0
    expected_price_inr_per_tonne: float = 0.0  # INR equivalent
    
    # Cost breakdown
    logistics_cost: Optional[LogisticsCost] = None
    logistics_cost_per_tonne: float = 0.0  # USD
    logistics_cost_inr_per_tonne: float = 0.0  # INR
    logistics_breakdown: Dict[str, float] = field(default_factory=dict)
    net_price_usd_per_tonne: float = 0.0
    net_price_inr_per_tonne: float = 0.0
    total_revenue_usd: float = 0.0
    total_revenue_inr: float = 0.0
    total_cost_usd: float = 0.0
    total_cost_inr: float = 0.0
    # Revenue minus logistics only. Production costs (seed, fertiliser, labour,
    # land) are NOT included — present these as "net after transport", not profit.
    net_profit_usd: float = 0.0
    net_profit_inr: float = 0.0
    
    # India-specific
    msp_price_inr_per_quintal: float = 0.0
    msp_procurement_months: List[int] = field(default_factory=list)
    
    # Farmer-specific
    estimated_production_tonnes: float = 0.0
    yield_kg_per_ha: float = 0.0
    harvest_peak_month: int = 1
    storage_capacity_months: int = 0
    risk_level: str = "moderate"
    
    # Logistics-specific
    transport_mode: str = "rail"
    transit_days: int = 0
    distance_km: float = 0.0
    storage_months: int = 0
    
    # Reasoning
    farmer_reasoning: str = ""
    market_reasoning: str = ""
    logistics_reasoning: str = ""
    consensus_reasoning: str = ""
    reasoning_trace: Dict[str, str] = field(default_factory=dict)
    
    # Negotiation history
    negotiation_rounds: List[Dict[str, Any]] = field(default_factory=list)
    
    # Confidence
    confidence_score: float = 0.0  # 0-1
    risk_factors: List[str] = field(default_factory=list)
    
    # Alternatives considered
    alternatives: List[Dict[str, Any]] = field(default_factory=list)
    
    # Price forecast (for UI)
    price_forecast: List[Dict[str, Any]] = field(default_factory=list)
    optimal_windows: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AgentMessage:
    """Message passed between agents."""
    sender: str
    recipient: str
    message_type: str  # "query", "response", "proposal", "counter_proposal", "final"
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])


# Harvest calendars for major crops (northern hemisphere defaults, adjusted per country)
HARVEST_CALENDARS = {
    (CropType.WHEAT, Country.USA): HarvestCalendar(
        crop=CropType.WHEAT, country=Country.USA,
        planting_months=[9, 10, 11],  # Winter wheat
        harvest_start_month=6, harvest_peak_months=[6, 7], harvest_end_month=8
    ),
    (CropType.WHEAT, Country.RUSSIA): HarvestCalendar(
        crop=CropType.WHEAT, country=Country.RUSSIA,
        planting_months=[8, 9], harvest_start_month=7, harvest_peak_months=[7, 8], harvest_end_month=9
    ),
    (CropType.WHEAT, Country.UKRAINE): HarvestCalendar(
        crop=CropType.WHEAT, country=Country.UKRAINE,
        planting_months=[8, 9], harvest_start_month=7, harvest_peak_months=[7, 8], harvest_end_month=9
    ),
    (CropType.WHEAT, Country.FRANCE): HarvestCalendar(
        crop=CropType.WHEAT, country=Country.FRANCE,
        planting_months=[10, 11], harvest_start_month=7, harvest_peak_months=[7, 8], harvest_end_month=8
    ),
    (CropType.WHEAT, Country.GERMANY): HarvestCalendar(
        crop=CropType.WHEAT, country=Country.GERMANY,
        planting_months=[10, 11], harvest_start_month=7, harvest_peak_months=[7, 8], harvest_end_month=8
    ),
    (CropType.WHEAT, Country.CANADA): HarvestCalendar(
        crop=CropType.WHEAT, country=Country.CANADA,
        planting_months=[5, 6], harvest_start_month=8, harvest_peak_months=[8, 9], harvest_end_month=10
    ),
    (CropType.WHEAT, Country.AUSTRALIA): HarvestCalendar(
        crop=CropType.WHEAT, country=Country.AUSTRALIA,
        planting_months=[5, 6], harvest_start_month=11, harvest_peak_months=[11, 12], harvest_end_month=1
    ),
    (CropType.WHEAT, Country.ARGENTINA): HarvestCalendar(
        crop=CropType.WHEAT, country=Country.ARGENTINA,
        planting_months=[5, 6], harvest_start_month=11, harvest_peak_months=[11, 12], harvest_end_month=1
    ),
    (CropType.MAIZE, Country.USA): HarvestCalendar(
        crop=CropType.MAIZE, country=Country.USA,
        planting_months=[4, 5], harvest_start_month=9, harvest_peak_months=[10, 11], harvest_end_month=12
    ),
    (CropType.MAIZE, Country.BRAZIL): HarvestCalendar(
        crop=CropType.MAIZE, country=Country.BRAZIL,
        planting_months=[9, 10], harvest_start_month=3, harvest_peak_months=[3, 4], harvest_end_month=5
    ),
    (CropType.MAIZE, Country.ARGENTINA): HarvestCalendar(
        crop=CropType.MAIZE, country=Country.ARGENTINA,
        planting_months=[9, 10], harvest_start_month=3, harvest_peak_months=[3, 4], harvest_end_month=5
    ),
    (CropType.MAIZE, Country.CHINA): HarvestCalendar(
        crop=CropType.MAIZE, country=Country.CHINA,
        planting_months=[4, 5], harvest_start_month=9, harvest_peak_months=[9, 10], harvest_end_month=11
    ),
    (CropType.RICE, Country.INDIA): HarvestCalendar(
        crop=CropType.RICE, country=Country.INDIA,
        planting_months=[6, 7], harvest_start_month=10, harvest_peak_months=[11, 12], harvest_end_month=1
    ),
    (CropType.WHEAT, Country.INDIA): HarvestCalendar(
        crop=CropType.WHEAT, country=Country.INDIA,
        planting_months=[10, 11], harvest_start_month=3, harvest_peak_months=[3, 4], harvest_end_month=5
    ),
    (CropType.MAIZE, Country.INDIA): HarvestCalendar(
        crop=CropType.MAIZE, country=Country.INDIA,
        planting_months=[6, 7], harvest_start_month=9, harvest_peak_months=[10, 11], harvest_end_month=12
    ),
    (CropType.SOYBEANS, Country.INDIA): HarvestCalendar(
        crop=CropType.SOYBEANS, country=Country.INDIA,
        planting_months=[6, 7], harvest_start_month=9, harvest_peak_months=[10, 11], harvest_end_month=11
    ),
    (CropType.RICE, Country.CHINA): HarvestCalendar(
        crop=CropType.RICE, country=Country.CHINA,
        planting_months=[4, 5], harvest_start_month=9, harvest_peak_months=[9, 10], harvest_end_month=11
    ),
    (CropType.RICE, Country.BRAZIL): HarvestCalendar(
        crop=CropType.RICE, country=Country.BRAZIL,
        planting_months=[10, 11], harvest_start_month=3, harvest_peak_months=[3, 4], harvest_end_month=5
    ),
    (CropType.SOYBEANS, Country.USA): HarvestCalendar(
        crop=CropType.SOYBEANS, country=Country.USA,
        planting_months=[5, 6], harvest_start_month=9, harvest_peak_months=[10, 11], harvest_end_month=11
    ),
    (CropType.SOYBEANS, Country.BRAZIL): HarvestCalendar(
        crop=CropType.SOYBEANS, country=Country.BRAZIL,
        planting_months=[10, 11], harvest_start_month=3, harvest_peak_months=[3, 4], harvest_end_month=5
    ),
    (CropType.SOYBEANS, Country.ARGENTINA): HarvestCalendar(
        crop=CropType.SOYBEANS, country=Country.ARGENTINA,
        planting_months=[10, 11], harvest_start_month=3, harvest_peak_months=[3, 4], harvest_end_month=5
    ),
}


def get_harvest_calendar(crop: CropType, country: Country) -> HarvestCalendar:
    """Get harvest calendar for a crop/country combination."""
    return HARVEST_CALENDARS.get(
        (crop, country),
        HarvestCalendar(crop=crop, country=country, harvest_start_month=1, harvest_end_month=12)
    )