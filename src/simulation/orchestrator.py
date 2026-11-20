"""
Simulation Orchestrator - Coordinates the three agents and produces sell recommendations.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
import json
import logging
from datetime import datetime

from ..agents.base import BaseAgent, AgentCoordinator
from ..agents.farmer import FarmerAgent
from ..agents.market import MarketAgent
from ..agents.logistics import LogisticsAgent
from ..agents.models import (
    CropType, Country, MarketRegion, SellRecommendation, 
    LogisticsCost, AgentMessage
)
from ..data.faostat_loader import FAOSTATLoader

# Optional LLM integration
try:
    from ..agents.llm_agents import create_llm_agents, LLMConfig
    LLM_AGENTS_AVAILABLE = True
except ImportError:
    LLM_AGENTS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class SimulationConfig:
    """Configuration for a simulation run."""
    crop: CropType
    country: Country
    production_year: int
    farm_size_ha: float = 1000.0
    target_markets: List[MarketRegion] = None
    risk_tolerance: str = "moderate"
    
    def __post_init__(self):
        if self.target_markets is None:
            self.target_markets = [MarketRegion.DOMESTIC, MarketRegion.EXPORT_ASIA]


class CropSellSimulation:
    """
    Main simulation class that orchestrates the three agents
    and produces a unified sell recommendation.
    Supports optional LLM-enhanced agents for enhanced decision-making.
    """

    def __init__(self, data_loader: FAOSTATLoader, config: Optional[SimulationConfig] = None,
                 llm_config: Optional["LLMConfig"] = None):
        self.data_loader = data_loader
        self.config = config or SimulationConfig(
            crop=CropType.WHEAT,
            country=Country.INDIA,
            production_year=2026,
        )
        self.llm_config = llm_config
        
        # Initialize agents (LLM-enhanced if available and configured)
        if llm_config and LLM_AGENTS_AVAILABLE and llm_config.enabled:
            logger.info("Initializing LLM-enhanced agents")
            llm_agents = create_llm_agents(llm_config)
            self.farmer = llm_agents["farmer"]
            self.market = llm_agents["market"]
            self.logistics = llm_agents["logistics"]
            self.coordinator = llm_agents["coordinator"]
        else:
            # Standard agents
            self.farmer = FarmerAgent("farmer_001", data_loader)
            self.market = MarketAgent("market_001", data_loader)
            self.logistics = LogisticsAgent("logistics_001")
            
            # Coordinator
            self.coordinator = AgentCoordinator()
            self.coordinator.register(self.farmer)
            self.coordinator.register(self.market)
            self.coordinator.register(self.logistics)
        
        # Results
        self.farmer_result: Dict[str, Any] = {}
        self.market_result: Dict[str, Any] = {}
        self.logistics_result: Dict[str, Any] = {}
        self.final_recommendation: Optional[SellRecommendation] = None

    def run(self) -> SellRecommendation:
        """Run the full simulation and return a sell recommendation."""
        logger.info(f"Starting simulation for {self.config.crop.value} in {self.config.country.value} ({self.config.production_year})")
        
        # Step 1: Run each agent independently
        self._run_agents()
        
        # Step 2: Cross-agent negotiation
        self._run_negotiation()
        
        # Step 3: Synthesize final recommendation
        self.final_recommendation = self._synthesize_recommendation()
        
        logger.info(f"Simulation complete. Recommendation: Sell in month {self.final_recommendation.recommended_sell_month} to {self.final_recommendation.recommended_market.value}")
        
        return self.final_recommendation

    def _run_agents(self):
        """Run each agent's analysis."""
        context = {
            "crop": self.config.crop.value,
            "country": self.config.country.value,
            "production_year": self.config.production_year,
            "farm_size_ha": self.config.farm_size_ha,
            "risk_tolerance": self.config.risk_tolerance,
            "target_markets": [m.value for m in self.config.target_markets]
        }
        
        # Farmer agent
        logger.info("Running Farmer Agent...")
        self.farmer_result = self.farmer.act(context)
        logger.info(f"Farmer: {self.farmer_result['production_estimate']['volume']:,.0f} tonnes estimated")
        
        # Market agent
        logger.info("Running Market Agent...")
        self.market_result = self.market.act(context)
        logger.info(f"Market: {len(self.market_result['optimal_sell_windows'])} optimal windows identified")
        
        # Logistics agent - needs volume from farmer
        context["volume_tonnes"] = self.farmer_result["production_estimate"]["volume"]
        context["available_months"] = self.farmer_result["sell_timing_preferences"]["preferred_months"]
        context["storage_capacity_months"] = self.farmer_result["sell_timing_preferences"]["storage_capacity_months"]
        
        logger.info("Running Logistics Agent...")
        self.logistics_result = self.logistics.act(context)
        logger.info(f"Logistics: Optimal market {self.logistics_result['optimal_logistics'].get('market', 'N/A')}")

    def _run_negotiation(self):
        """Run multi-agent negotiation to reach consensus."""
        logger.info("Starting multi-agent negotiation...")
        
        # Initial proposal based on each agent's top preference
        farmer_prefs = self.farmer_result["sell_timing_preferences"]
        market_windows = self.market_result["optimal_sell_windows"]
        logistics_optimal = self.logistics_result["optimal_logistics"]
        
        # Build initial proposal
        if market_windows:
            best_market_window = market_windows[0]
            initial_proposal = {
                "sell_month": best_market_window["month"],
                "market": logistics_optimal.get("market", "domestic"),
                "price_usd_per_tonne": best_market_window["price_usd_per_tonne"],
                "volume_tonnes": self.farmer_result["production_estimate"]["volume"]
            }
        else:
            # Fallback
            initial_proposal = {
                "sell_month": farmer_prefs["preferred_months"][0],
                "market": "domestic",
                "price_usd_per_tonne": 200.0,
                "volume_tonnes": self.farmer_result["production_estimate"]["volume"]
            }
        
        # Track negotiation history for UI
        self._negotiation_history = []
        
        # Run negotiation rounds
        for round_num in range(3):
            logger.info(f"Negotiation round {round_num + 1}")
            
            # Get evaluations from each agent
            farmer_eval = self.farmer._evaluate_sell_proposal(initial_proposal)
            market_eval = self.market._evaluate_market_proposal(initial_proposal)
            logistics_eval = self.logistics._evaluate_logistics_proposal(initial_proposal)
            
            # Add accept field based on score threshold
            farmer_eval["accept"] = farmer_eval["score"] > 0.6
            market_eval["accept"] = market_eval["score"] > 0.6
            logistics_eval["accept"] = logistics_eval["score"] > 0.5
            
            # Record this round
            self._negotiation_history.append({
                "round": round_num + 1,
                "proposal": initial_proposal.copy(),
                "evaluations": {
                    "farmer": farmer_eval,
                    "market": market_eval,
                    "logistics": logistics_eval
                }
            })
            
            # Check consensus
            all_accept = all([
                farmer_eval["accept"],
                market_eval["accept"],
                logistics_eval["accept"]
            ])
            
            if all_accept:
                logger.info("Consensus reached!")
                break
            
            # Adjust proposal based on counter-terms
            initial_proposal = self._adjust_proposal(initial_proposal, farmer_eval, market_eval, logistics_eval)
        
        # Store final proposal and evaluations for synthesis
        self._final_proposal = initial_proposal
        self._evaluations = {
            "farmer": farmer_eval,
            "market": market_eval,
            "logistics": logistics_eval
        }

    def _adjust_proposal(self, proposal: Dict, farmer_eval: Dict, market_eval: Dict, logistics_eval: Dict) -> Dict:
        """Adjust proposal based on agent evaluations."""
        new_proposal = proposal.copy()
        
        # Prioritize counter-terms
        counters = []
        for eval_result, agent_name in [(farmer_eval, "farmer"), (market_eval, "market"), (logistics_eval, "logistics")]:
            if eval_result.get("counter_terms"):
                counters.append((eval_result["counter_terms"], agent_name, eval_result["score"]))
        
        # Sort by score (lowest score = most urgent adjustment)
        counters.sort(key=lambda x: x[2])
        
        for counter, agent, score in counters:
            if "suggested_month" in counter:
                new_proposal["sell_month"] = counter["suggested_month"]
                logger.info(f"Adjusted sell month to {counter['suggested_month']} based on {agent} feedback")
            if "suggested_price" in counter:
                new_proposal["price_usd_per_tonne"] = counter["suggested_price"]
            if "suggested_storage_months" in counter:
                # This would affect logistics cost
                pass
        
        return new_proposal

    def _synthesize_recommendation(self) -> SellRecommendation:
        """Synthesize final sell recommendation from all agent outputs."""
        final_proposal = getattr(self, '_final_proposal', {})
        evaluations = getattr(self, '_evaluations', {})
        
        # Get key data
        prod_est = self.farmer_result["production_estimate"]
        farmer_prefs = self.farmer_result["sell_timing_preferences"]
        market_windows = self.market_result["optimal_sell_windows"]
        logistics_optimal = self.logistics_result["optimal_logistics"]
        
        # Determine final values
        sell_month = final_proposal.get("sell_month", farmer_prefs["preferred_months"][0])
        market = final_proposal.get("market", logistics_optimal.get("market", "domestic"))
        price_usd = final_proposal.get("price_usd_per_tonne", market_windows[0]["price_usd_per_tonne"] if market_windows else 200.0)
        volume = prod_est["volume"]
        
        # Get logistics cost for this combination - calculate storage months correctly
        storage_months = self._calculate_storage_months(sell_month)
        logistics_cost_data = self.logistics._calculate_full_logistics_cost(
            market, volume, storage_months
        )
        
        if logistics_cost_data:
            logistics_cost = LogisticsCost(
                origin_country=self.config.country,
                destination_region=MarketRegion(market),
                transport_mode=logistics_cost_data["mode"],
                distance_km=logistics_cost_data["distance_km"],
                transport_cost_usd_per_tonne=logistics_cost_data["transport_cost_usd_per_tonne"],
                storage_cost_usd_per_tonne_per_month=logistics_cost_data["storage_cost_usd_per_tonne"] / max(1, storage_months),
                handling_cost_usd_per_tonne=logistics_cost_data["handling_cost_usd_per_tonne"],
                insurance_cost_usd_per_tonne=logistics_cost_data["insurance_cost_usd_per_tonne"],
                transit_time_days=logistics_cost_data["transit_time_days"],
                total_cost_usd_per_tonne=logistics_cost_data["total_cost_usd_per_tonne"]
            )
        else:
            logistics_cost = LogisticsCost(
                origin_country=self.config.country,
                destination_region=MarketRegion(market),
                transport_mode="ocean_vessel",
                distance_km=10000,
                transport_cost_usd_per_tonne=150,
                storage_cost_usd_per_tonne_per_month=2.5,
                handling_cost_usd_per_tonne=10,
                insurance_cost_usd_per_tonne=5,
                transit_time_days=30,
                total_cost_usd_per_tonne=170
            )
        
        # Calculate financials (USD)
        net_price_usd = price_usd - logistics_cost.total_cost_usd_per_tonne
        total_revenue_usd = price_usd * volume
        total_cost_usd = logistics_cost.total_cost_usd_per_tonne * volume
        net_profit_usd = net_price_usd * volume
        
        # INR conversion (approximate, Nov 2026)
        from ..agents.models import USD_TO_INR
        usd_to_inr = USD_TO_INR if self.config.country == Country.INDIA else 1.0
        price_inr = price_usd * usd_to_inr
        logistics_cost_inr = logistics_cost.total_cost_usd_per_tonne * usd_to_inr
        net_price_inr = net_price_usd * usd_to_inr
        total_revenue_inr = total_revenue_usd * usd_to_inr
        total_cost_inr = total_cost_usd * usd_to_inr
        net_profit_inr = net_profit_usd * usd_to_inr
        
        # Logistics breakdown in INR
        logistics_breakdown = {
            "transport_inr": logistics_cost_data.get("transport_cost_usd_per_tonne", 0) * usd_to_inr if logistics_cost_data else 0,
            "storage_inr": logistics_cost_data.get("storage_cost_usd_per_tonne", 0) * usd_to_inr if logistics_cost_data else 0,
            "handling_inr": logistics_cost_data.get("handling_cost_usd_per_tonne", 0) * usd_to_inr if logistics_cost_data else 0,
            "insurance_inr": logistics_cost_data.get("insurance_cost_usd_per_tonne", 0) * usd_to_inr if logistics_cost_data else 0,
        }
        
        # Confidence score
        farmer_conf = prod_est["confidence"]
        market_conf = evaluations.get("market", {}).get("score", 0.7)
        logistics_conf = evaluations.get("logistics", {}).get("score", 0.7)
        confidence = (farmer_conf + market_conf + logistics_conf) / 3.0
        
        # Risk factors
        risk_factors = []
        risk_factors.extend(self.farmer_result["risk_assessment"].get("factors", []))
        if self.market_result["market_analysis"].get("volatility", 0) > 0.2:
            risk_factors.append("High price volatility")
        if logistics_cost.total_cost_usd_per_tonne > 100:
            risk_factors.append("High logistics costs")
        if storage_months > farmer_prefs["storage_capacity_months"]:
            risk_factors.append("Storage duration exceeds capacity")
        
        # Alternatives
        alternatives = []
        for window in market_windows[1:3]:
            alt_logistics = self.logistics._calculate_full_logistics_cost(
                window.get("market", market), volume,
                self._calculate_storage_months(window["month"])
            )
            if alt_logistics:
                alt_net_usd = window["price_usd_per_tonne"] - alt_logistics["total_cost_usd_per_tonne"]
                alternatives.append({
                    "month": window["month"],
                    "market": window.get("market", market),
                    "price_usd": window["price_usd_per_tonne"],
                    "price_inr": window["price_usd_per_tonne"] * usd_to_inr,
                    "net_price_usd": alt_net_usd,
                    "net_price_inr": alt_net_usd * usd_to_inr,
                    "logistics_cost_usd": alt_logistics["total_cost_usd_per_tonne"],
                    "logistics_cost_inr": alt_logistics["total_cost_usd_per_tonne"] * usd_to_inr,
                    "reason": window.get("reason", "Alternative window"),
                    "confidence": window.get("confidence", 0.5)
                })
        
        # Negotiation rounds for UI
        negotiation_rounds = []
        if hasattr(self, '_negotiation_history'):
            for round_data in self._negotiation_history:
                negotiation_rounds.append(round_data)
        
        # India-specific MSP from the shared 2026-27 official table
        from ..agents.models import INDIA_MSP_2026_27
        msp_price = 0.0
        msp_months = []
        if self.config.country == Country.INDIA:
            msp_price = INDIA_MSP_2026_27.get(self.config.crop, 0.0)
            msp_months = [4, 5, 6] if self.config.crop == CropType.WHEAT else [10, 11, 12]
        
        # Price forecast and optimal windows for UI
        price_forecast = self.market_result.get("price_forecast", [])
        optimal_windows = self.market_result.get("optimal_sell_windows", [])
        
        # Build recommendation with all fields
        recommendation = SellRecommendation(
            crop=self.config.crop,
            country=self.config.country,
            production_year=self.config.production_year,
            available_volume_tonnes=volume,
            recommended_sell_month=sell_month,
            recommended_market=MarketRegion(market),
            expected_price_usd_per_tonne=price_usd,
            expected_price_inr_per_tonne=price_inr,
            logistics_cost=logistics_cost,
            logistics_cost_per_tonne=logistics_cost.total_cost_usd_per_tonne,
            logistics_cost_inr_per_tonne=logistics_cost_inr,
            logistics_breakdown=logistics_breakdown,
            net_price_usd_per_tonne=net_price_usd,
            net_price_inr_per_tonne=net_price_inr,
            total_revenue_usd=total_revenue_usd,
            total_revenue_inr=total_revenue_inr,
            total_cost_usd=total_cost_usd,
            total_cost_inr=total_cost_inr,
            net_profit_usd=net_profit_usd,
            net_profit_inr=net_profit_inr,
            msp_price_inr_per_quintal=msp_price,
            msp_procurement_months=msp_months,
            estimated_production_tonnes=prod_est["volume"],
            yield_kg_per_ha=prod_est.get("yield", 0),
            harvest_peak_month=self.farmer_result["harvest_calendar"]["harvest_peak"][0] if self.farmer_result.get("harvest_calendar", {}).get("harvest_peak") else 1,
            storage_capacity_months=farmer_prefs.get("storage_capacity_months", 0),
            risk_level=self.farmer_result["risk_assessment"].get("level", "moderate"),
            transport_mode=logistics_cost_data.get("mode", "rail") if logistics_cost_data else "rail",
            transit_days=logistics_cost_data.get("transit_time_days", 0) if logistics_cost_data else 0,
            distance_km=logistics_cost_data.get("distance_km", 0) if logistics_cost_data else 0,
            storage_months=storage_months,
            farmer_reasoning=self.farmer_result.get("reasoning", ""),
            market_reasoning=self.market_result.get("reasoning", ""),
            logistics_reasoning=self.logistics_result.get("reasoning", ""),
            consensus_reasoning=self._generate_consensus_reasoning(evaluations),
            reasoning_trace={
                "farmer": self.farmer_result.get("reasoning", ""),
                "market": self.market_result.get("reasoning", ""),
                "logistics": self.logistics_result.get("reasoning", ""),
            },
            negotiation_rounds=negotiation_rounds,
            confidence_score=confidence,
            risk_factors=risk_factors,
            alternatives=alternatives,
            price_forecast=price_forecast,
            optimal_windows=optimal_windows
        )
        
        return recommendation

    def _get_harvest_end_month(self) -> int:
        """Get harvest end month for the crop/country."""
        from ..agents.models import get_harvest_calendar
        calendar = get_harvest_calendar(self.config.crop, self.config.country)
        return calendar.harvest_end_month

    def _calculate_storage_months(self, sell_month: int) -> int:
        """Calculate storage months needed for a given sell month.
        
        Handles year-wrap harvests (e.g., rice in India: harvest Oct-Jan).
        If selling during harvest period, storage = 0.
        If selling after harvest, storage = months since harvest end.
        """
        from ..agents.models import get_harvest_calendar
        calendar = get_harvest_calendar(self.config.crop, self.config.country)
        harvest_start = calendar.harvest_start_month
        harvest_end = calendar.harvest_end_month
        harvest_peak = calendar.harvest_peak_months
        
        # Check if sell_month is in harvest window (handles year-wrap)
        if harvest_end >= harvest_start:
            # Normal case: no year-wrap (e.g., wheat: Mar-May)
            in_harvest = harvest_start <= sell_month <= harvest_end
        else:
            # Year-wrap: harvest spans year boundary (e.g., rice: Oct-Jan)
            in_harvest = sell_month >= harvest_start or sell_month <= harvest_end
        
        # Also consider peak months as in-harvest
        in_harvest = in_harvest or (sell_month in harvest_peak)
        
        if in_harvest:
            return 0
        
        # Selling after harvest - calculate months since harvest end
        if harvest_end >= harvest_start:
            # Normal: harvest ended this year
            return max(0, sell_month - harvest_end)
        else:
            # Year-wrap: harvest ended in Jan/Feb of NEXT year
            # If selling before harvest starts (e.g., Feb-May for rice), 
            # it's after harvest end of previous cycle
            if sell_month < harvest_start:
                return sell_month  # months since Jan harvest end
            else:
                # Selling after harvest start but not in harvest - shouldn't happen
                return 0

    def _generate_consensus_reasoning(self, evaluations: Dict) -> str:
        """Generate consensus reasoning from all evaluations."""
        parts = []
        for agent_name, eval_data in evaluations.items():
            if isinstance(eval_data, dict) and "reasoning" in eval_data:
                parts.append(f"{agent_name.title()}: {eval_data['reasoning']}")
        return " | ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Convert simulation results to dictionary for serialization."""
        return {
            "config": {
                "crop": self.config.crop.value,
                "country": self.config.country.value,
                "production_year": self.config.production_year,
                "farm_size_ha": self.config.farm_size_ha,
                "target_markets": [m.value for m in self.config.target_markets]
            },
            "farmer_analysis": self.farmer_result,
            "market_analysis": self.market_result,
            "logistics_analysis": self.logistics_result,
            "recommendation": asdict(self.final_recommendation) if self.final_recommendation else None,
            "message_log": [
                {
                    "sender": m.sender,
                    "recipient": m.recipient,
                    "type": m.message_type,
                    "payload": m.payload,
                    "timestamp": m.timestamp.isoformat()
                }
                for m in self.coordinator.get_message_log()
            ]
        }

    def save_results(self, filepath: str):
        """Save simulation results to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
        logger.info(f"Results saved to {filepath}")


def run_simulation(crop: str, country: str, year: int = 2026, 
                   farm_size: float = 1000.0, 
                   data_dir: str = "data",
                   llm_config: Optional["LLMConfig"] = None) -> SellRecommendation:
    """Convenience function to run a simulation.
    
    Args:
        crop: Crop type (e.g., 'wheat', 'rice_paddy', 'maize')
        country: Country (e.g., 'india', 'usa', 'brazil')
        year: Production year
        farm_size: Farm size in hectares
        data_dir: Directory containing FAOSTAT ZIP files
        llm_config: Optional LLM configuration for enhanced agents
    """
    loader = FAOSTATLoader(data_dir)
    config = SimulationConfig(
        crop=CropType(crop),
        country=Country(country),
        production_year=year,
        farm_size_ha=farm_size
    )
    sim = CropSellSimulation(loader, config, llm_config)
    return sim.run()