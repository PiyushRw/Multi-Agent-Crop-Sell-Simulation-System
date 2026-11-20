"""
Crop Sell Simulation - Multi-Agent System for Optimal Crop Selling Decisions

This package implements a simulation with three cooperating agents:
- Farmer Agent: Production planning, harvest timing, volume estimation
- Market Agent: Price analysis, forecasting, market opportunity identification 
- Logistics Agent: Transport, storage, and handling cost optimization

Together they recommend the best time and place to sell a crop using real FAOSTAT data.
"""

from .agents.models import (
    CropType, Country, MarketRegion, TransportMode,
    PricePoint, ProductionData, HarvestCalendar,
    LogisticsCost, SellRecommendation, AgentMessage,
    get_harvest_calendar
)
from .agents.base import BaseAgent, AgentCoordinator, AgentState
from .agents.farmer import FarmerAgent, FarmerContext
from .agents.market import MarketAgent, MarketContext
from .agents.logistics import LogisticsAgent, LogisticsContext

from .data.faostat_loader import FAOSTATLoader, load_faostat, CROP_CODES, COUNTRY_CODES

from .simulation.orchestrator import CropSellSimulation, SimulationConfig, run_simulation

__version__ = "1.0.0"
__author__ = "Piyush Rawat"

__all__ = [
    # Models
    "CropType", "Country", "MarketRegion", "TransportMode",
    "PricePoint", "ProductionData", "HarvestCalendar",
    "LogisticsCost", "SellRecommendation", "AgentMessage",
    "get_harvest_calendar",
    
    # Agents
    "BaseAgent", "AgentCoordinator", "AgentState",
    "FarmerAgent", "FarmerContext",
    "MarketAgent", "MarketContext",
    "LogisticsAgent", "LogisticsContext",
    
    # Data
    "FAOSTATLoader", "load_faostat", "CROP_CODES", "COUNTRY_CODES",
    
    # Simulation
    "CropSellSimulation", "SimulationConfig", "run_simulation",
]