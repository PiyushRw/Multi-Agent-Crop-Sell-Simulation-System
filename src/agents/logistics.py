"""
Logistics Agent - Calculates transport, storage, and handling costs.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import numpy as np
import logging

from .base import BaseAgent
from .models import (
    CropType, Country, MarketRegion, TransportMode, LogisticsCost, 
    AgentMessage, SellRecommendation, get_harvest_calendar
)

logger = logging.getLogger(__name__)


@dataclass
class LogisticsContext:
    """Context for the logistics agent."""
    crop: CropType
    origin_country: Country
    volume_tonnes: float
    available_months: List[int]  # When crop is available for shipment
    storage_capacity_months: int = 12


class LogisticsAgent(BaseAgent):
    """
    Logistics Agent - Responsible for:
    - Transport cost calculation (multiple modes)
    - Storage cost estimation
    - Route optimization
    - Transit time estimation
    - Risk assessment for logistics
    """

    # Transport cost parameters (USD/tonne/km) - simplified estimates
    TRANSPORT_COSTS = {
        TransportMode.TRUCK: 0.08,
        TransportMode.RAIL: 0.04,
        TransportMode.BARGE: 0.025,
        TransportMode.OCEAN_VESSEL: 0.015,
        TransportMode.CONTAINER: 0.03,
    }
    
    # Fixed costs per shipment
    FIXED_COSTS = {
        TransportMode.TRUCK: 50,
        TransportMode.RAIL: 200,
        TransportMode.BARGE: 150,
        TransportMode.OCEAN_VESSEL: 500,
        TransportMode.CONTAINER: 300,
    }
    
    # Storage costs (USD/tonne/month)
    STORAGE_COSTS = {
        CropType.WHEAT: 2.5,
        CropType.MAIZE: 2.5,
        CropType.RICE: 3.0,
        CropType.SOYBEANS: 2.8,
        CropType.BARLEY: 2.5,
        CropType.SORGHUM: 2.5,
    }
    
    # Handling costs (USD/tonne)
    HANDLING_COSTS = {
        TransportMode.TRUCK: 5,
        TransportMode.RAIL: 8,
        TransportMode.BARGE: 6,
        TransportMode.OCEAN_VESSEL: 12,
        TransportMode.CONTAINER: 15,
    }
    
    # Insurance rates (% of cargo value per month)
    INSURANCE_RATES = {
        TransportMode.TRUCK: 0.002,
        TransportMode.RAIL: 0.0015,
        TransportMode.BARGE: 0.001,
        TransportMode.OCEAN_VESSEL: 0.003,
        TransportMode.CONTAINER: 0.0025,
    }

    # Distance matrix (km) between major origins and market regions
    DISTANCES = {
        (Country.USA, MarketRegion.DOMESTIC): 500,
        (Country.USA, MarketRegion.EXPORT_NORTH_AMERICA): 800,
        (Country.USA, MarketRegion.EXPORT_SOUTH_AMERICA): 6000,
        (Country.USA, MarketRegion.EXPORT_EUROPE): 7000,
        (Country.USA, MarketRegion.EXPORT_ASIA): 11000,
        (Country.USA, MarketRegion.EXPORT_AFRICA): 12000,
        (Country.USA, MarketRegion.EXPORT_MIDDLE_EAST): 11500,
        
        (Country.BRAZIL, MarketRegion.DOMESTIC): 800,
        (Country.BRAZIL, MarketRegion.EXPORT_NORTH_AMERICA): 6000,
        (Country.BRAZIL, MarketRegion.EXPORT_SOUTH_AMERICA): 2000,
        (Country.BRAZIL, MarketRegion.EXPORT_EUROPE): 9000,
        (Country.BRAZIL, MarketRegion.EXPORT_ASIA): 18000,
        (Country.BRAZIL, MarketRegion.EXPORT_AFRICA): 7000,
        (Country.BRAZIL, MarketRegion.EXPORT_MIDDLE_EAST): 11000,
        
        (Country.ARGENTINA, MarketRegion.DOMESTIC): 600,
        (Country.ARGENTINA, MarketRegion.EXPORT_NORTH_AMERICA): 10000,
        (Country.ARGENTINA, MarketRegion.EXPORT_SOUTH_AMERICA): 2500,
        (Country.ARGENTINA, MarketRegion.EXPORT_EUROPE): 11000,
        (Country.ARGENTINA, MarketRegion.EXPORT_ASIA): 19000,
        (Country.ARGENTINA, MarketRegion.EXPORT_AFRICA): 9000,
        
        (Country.RUSSIA, MarketRegion.DOMESTIC): 1500,
        (Country.RUSSIA, MarketRegion.EXPORT_NORTH_AMERICA): 8000,
        (Country.RUSSIA, MarketRegion.EXPORT_EUROPE): 3000,
        (Country.RUSSIA, MarketRegion.EXPORT_ASIA): 5000,
        (Country.RUSSIA, MarketRegion.EXPORT_MIDDLE_EAST): 4000,
        
        (Country.UKRAINE, MarketRegion.DOMESTIC): 500,
        (Country.UKRAINE, MarketRegion.EXPORT_EUROPE): 2000,
        (Country.UKRAINE, MarketRegion.EXPORT_ASIA): 7000,
        (Country.UKRAINE, MarketRegion.EXPORT_AFRICA): 4000,
        (Country.UKRAINE, MarketRegion.EXPORT_MIDDLE_EAST): 2500,

        (Country.INDIA, MarketRegion.DOMESTIC): 1200,
        (Country.INDIA, MarketRegion.EXPORT_ASIA): 4500,
        (Country.INDIA, MarketRegion.EXPORT_MIDDLE_EAST): 3800,
        (Country.INDIA, MarketRegion.EXPORT_EUROPE): 7500,
        (Country.INDIA, MarketRegion.EXPORT_AFRICA): 6000,

        (Country.CANADA, MarketRegion.DOMESTIC): 1000,
        (Country.CANADA, MarketRegion.EXPORT_NORTH_AMERICA): 1500,
        (Country.CANADA, MarketRegion.EXPORT_EUROPE): 5500,
        (Country.CANADA, MarketRegion.EXPORT_ASIA): 9000,
        
        (Country.AUSTRALIA, MarketRegion.DOMESTIC): 1000,
        (Country.AUSTRALIA, MarketRegion.EXPORT_ASIA): 6000,
        (Country.AUSTRALIA, MarketRegion.EXPORT_EUROPE): 16000,
        (Country.AUSTRALIA, MarketRegion.EXPORT_MIDDLE_EAST): 11000,
        
        (Country.FRANCE, MarketRegion.DOMESTIC): 400,
        (Country.FRANCE, MarketRegion.EXPORT_EUROPE): 800,
        (Country.FRANCE, MarketRegion.EXPORT_AFRICA): 3000,
        (Country.FRANCE, MarketRegion.EXPORT_MIDDLE_EAST): 3500,
        
        (Country.GERMANY, MarketRegion.DOMESTIC): 300,
        (Country.GERMANY, MarketRegion.EXPORT_EUROPE): 600,
        (Country.GERMANY, MarketRegion.EXPORT_ASIA): 9000,
    }

    # Transit times (days)
    TRANSIT_TIMES = {
        (TransportMode.TRUCK, 0, 1000): 3,
        (TransportMode.TRUCK, 1000, 3000): 7,
        (TransportMode.TRUCK, 3000, 10000): 14,
        
        (TransportMode.RAIL, 0, 2000): 5,
        (TransportMode.RAIL, 2000, 5000): 10,
        (TransportMode.RAIL, 5000, 10000): 18,
        
        (TransportMode.BARGE, 0, 2000): 10,
        (TransportMode.BARGE, 2000, 5000): 20,
        
        (TransportMode.OCEAN_VESSEL, 0, 5000): 20,
        (TransportMode.OCEAN_VESSEL, 5000, 10000): 30,
        (TransportMode.OCEAN_VESSEL, 10000, 20000): 40,
        
        (TransportMode.CONTAINER, 0, 5000): 15,
        (TransportMode.CONTAINER, 5000, 10000): 25,
        (TransportMode.CONTAINER, 10000, 20000): 35,
    }

    def __init__(self, agent_id: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(agent_id, "logistics", config)
        self.logistics_context: Optional[LogisticsContext] = None

    def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Process incoming messages from other agents."""
        if message.message_type == "query":
            return self._handle_query(message)
        elif message.message_type == "proposal":
            return self._handle_proposal(message)
        elif message.message_type == "counter_proposal":
            return self._handle_counter_proposal(message)
        return None

    def _handle_query(self, message: AgentMessage) -> AgentMessage:
        """Handle query messages."""
        query_type = message.payload.get("query_type")
        
        if query_type == "transport_options":
            options = self._get_transport_options(
                message.payload.get("destination", "domestic"),
                message.payload.get("volume_tonnes", 1000)
            )
            return AgentMessage(
                sender=self.state.agent_id,
                recipient=message.sender,
                message_type="response",
                payload={"query_type": "transport_options", "options": options}
            )
        
        elif query_type == "storage_cost":
            months = message.payload.get("months", 1)
            cost = self._calculate_storage_cost(months)
            return AgentMessage(
                sender=self.state.agent_id,
                recipient=message.sender,
                message_type="response",
                payload={"query_type": "storage_cost", "months": months, "cost_usd_per_tonne": cost}
            )
        
        elif query_type == "full_logistics_cost":
            dest = message.payload.get("destination", "domestic")
            volume = message.payload.get("volume_tonnes", 1000)
            month = message.payload.get("month", 1)
            cost = self._calculate_full_logistics_cost(dest, volume, month)
            return AgentMessage(
                sender=self.state.agent_id,
                recipient=message.sender,
                message_type="response",
                payload={"query_type": "full_logistics_cost", "cost": cost}
            )
        
        return AgentMessage(
            sender=self.state.agent_id,
            recipient=message.sender,
            message_type="response",
            payload={"error": f"Unknown query type: {query_type}"}
        )

    def _handle_proposal(self, message: AgentMessage) -> AgentMessage:
        """Evaluate a sell proposal from logistics perspective."""
        proposal = message.payload.get("proposal", {})
        evaluation = self._evaluate_logistics_proposal(proposal)
        
        return AgentMessage(
            sender=self.state.agent_id,
            recipient=message.sender,
            message_type="response",
            payload={
                "evaluation": evaluation,
                "accept": evaluation["score"] > 0.5,
                "counter_terms": evaluation.get("counter_terms"),
                "reasoning": evaluation["reasoning"]
            }
        )

    def _handle_counter_proposal(self, message: AgentMessage) -> AgentMessage:
        return self._handle_proposal(message)

    def act(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Main action: calculate logistics costs for all market options."""
        self.logistics_context = LogisticsContext(
            crop=CropType(context.get("crop", "wheat")),
            origin_country=Country(context.get("country", "india")),
            volume_tonnes=context.get("volume_tonnes", 1000),
            available_months=context.get("available_months", list(range(1, 13))),
            storage_capacity_months=context.get("storage_capacity_months", 12)
        )
        
        # Calculate costs for each target market
        market_costs = {}
        for market in MarketRegion:
            cost = self._calculate_full_logistics_cost(market.value, self.logistics_context.volume_tonnes)
            if cost:
                market_costs[market.value] = cost
        
        # Find optimal logistics option
        optimal = self._find_optimal_logistics(market_costs)
        
        return {
            "agent": "logistics",
            "crop": self.logistics_context.crop.value,
            "origin_country": self.logistics_context.origin_country.value,
            "volume_tonnes": self.logistics_context.volume_tonnes,
            "market_costs": market_costs,
            "optimal_logistics": optimal,
            "reasoning": self._generate_reasoning(market_costs, optimal)
        }

    def _get_transport_options(self, destination: str, volume_tonnes: float) -> List[Dict[str, Any]]:
        """Get available transport options for a destination."""
        market = MarketRegion(destination)
        origin = self.logistics_context.origin_country
        
        distance = self.DISTANCES.get((origin, market), 10000)
        
        options = []
        for mode in TransportMode:
            cost = self._calculate_transport_cost(mode, distance, volume_tonnes)
            transit = self._estimate_transit_time(mode, distance)
            
            options.append({
                "mode": mode.value,
                "distance_km": distance,
                "transport_cost_usd_per_tonne": round(cost["variable"] + cost["fixed"] / volume_tonnes, 2),
                "fixed_cost_usd": cost["fixed"],
                "variable_cost_usd_per_tonne": cost["variable"],
                "transit_time_days": transit,
                "suitable": self._is_mode_suitable(mode, distance, market)
            })
        
        return options

    def _calculate_transport_cost(self, mode: TransportMode, distance_km: float, volume_tonnes: float) -> Dict[str, float]:
        """Calculate transport cost for a mode."""
        rate = self.TRANSPORT_COSTS.get(mode, 0.05)
        fixed = self.FIXED_COSTS.get(mode, 100)
        
        variable_cost = rate * distance_km
        total_variable = variable_cost * volume_tonnes
        
        return {
            "fixed": fixed,
            "variable": variable_cost,
            "total": fixed + total_variable
        }

    def _estimate_transit_time(self, mode: TransportMode, distance_km: float) -> int:
        """Estimate transit time in days."""
        for (m, d_min, d_max), time in self.TRANSIT_TIMES.items():
            if m == mode and d_min <= distance_km <= d_max:
                return time
        
        # Default estimates
        defaults = {
            TransportMode.TRUCK: max(1, int(distance_km / 500)),
            TransportMode.RAIL: max(2, int(distance_km / 800)),
            TransportMode.BARGE: max(5, int(distance_km / 300)),
            TransportMode.OCEAN_VESSEL: max(10, int(distance_km / 400)),
            TransportMode.CONTAINER: max(10, int(distance_km / 500)),
        }
        return defaults.get(mode, int(distance_km / 500))

    def _calculate_storage_cost(self, months: int) -> float:
        """Calculate storage cost for given months."""
        if not self.logistics_context:
            return 0.0
        
        crop = self.logistics_context.crop
        monthly_rate = self.STORAGE_COSTS.get(crop, 2.5)
        
        # Diminishing marginal cost for longer storage
        if months <= 3:
            return monthly_rate * months
        elif months <= 6:
            return monthly_rate * 3 + monthly_rate * 0.9 * (months - 3)
        else:
            return monthly_rate * 3 + monthly_rate * 0.9 * 3 + monthly_rate * 0.8 * (months - 6)

    def _calculate_full_logistics_cost(self, destination: str, volume_tonnes: float, 
                                        storage_months: int = 0) -> Optional[Dict[str, Any]]:
        """Calculate complete logistics cost for a destination."""
        market = MarketRegion(destination)
        origin = self.logistics_context.origin_country
        
        distance = self.DISTANCES.get((origin, market))
        if distance is None:
            return None
        
        # Determine best transport mode
        options = self._get_transport_options(destination, volume_tonnes)
        suitable = [o for o in options if o["suitable"]]
        if not suitable:
            suitable = options
        
        # Choose lowest cost suitable option
        best = min(suitable, key=lambda x: x["transport_cost_usd_per_tonne"])
        mode = TransportMode(best["mode"])
        
        transport_cost = best["transport_cost_usd_per_tonne"]
        transit_time = best["transit_time_days"]
        
        # Storage cost
        storage_cost = self._calculate_storage_cost(storage_months)
        
        # Handling cost
        handling_cost = self.HANDLING_COSTS.get(mode, 10)
        
        # Insurance (based on estimated cargo value ~$250/tonne)
        cargo_value_per_tonne = 250  # Rough estimate in USD
        insurance_rate = self.INSURANCE_RATES.get(mode, 0.002)
        insurance_cost = cargo_value_per_tonne * insurance_rate * max(1, transit_time / 30 + storage_months)
        
        total = transport_cost + storage_cost + handling_cost + insurance_cost
        
        return {
            "destination": destination,
            "mode": mode.value,
            "distance_km": distance,
            "transport_cost_usd_per_tonne": round(transport_cost, 2),
            "storage_cost_usd_per_tonne": round(storage_cost, 2),
            "handling_cost_usd_per_tonne": round(handling_cost, 2),
            "insurance_cost_usd_per_tonne": round(insurance_cost, 2),
            "transit_time_days": transit_time,
            "total_cost_usd_per_tonne": round(total, 2),
            "storage_months": storage_months
        }

    def _is_mode_suitable(self, mode: TransportMode, distance: float, market: MarketRegion) -> bool:
        """Check if transport mode is suitable for the route."""
        if market == MarketRegion.DOMESTIC:
            # For India, barge is not practical for domestic grain transport
            # (no major inland waterways connecting production to consumption centers)
            if hasattr(self, 'logistics_context') and self.logistics_context and \
               self.logistics_context.origin_country == Country.INDIA:
                return mode in [TransportMode.TRUCK, TransportMode.RAIL]
            return mode in [TransportMode.TRUCK, TransportMode.RAIL, TransportMode.BARGE]
        elif market in [MarketRegion.EXPORT_NORTH_AMERICA, MarketRegion.EXPORT_SOUTH_AMERICA]:
            return mode in [TransportMode.OCEAN_VESSEL, TransportMode.CONTAINER]
        else:
            return mode in [TransportMode.OCEAN_VESSEL, TransportMode.CONTAINER]

    def _find_optimal_logistics(self, market_costs: Dict[str, Dict]) -> Dict[str, Any]:
        """Find the optimal logistics option."""
        if not market_costs:
            return {}

        # Score each option: lower cost is better, but also consider transit time
        scored = []
        for market, cost in market_costs.items():
            total = cost["total_cost_usd_per_tonne"]
            transit = cost["transit_time_days"]

            # Costs are USD/tonne; ₹4000/t ≈ $48/t at 83 INR/USD.
            # Dividing USD by 4000 made every option look equally cheap.
            cost_score = 1.0 / (1.0 + total / 48.0)
            time_score = 1.0 / (1.0 + transit / 20.0)  # Normalize around 20 days

            combined = 0.7 * cost_score + 0.3 * time_score

            scored.append({
                "market": market,
                "total_cost": total,
                "transit_days": transit,
                "combined_score": combined,
                "details": cost
            })

        scored.sort(key=lambda x: x["combined_score"], reverse=True)
        return scored[0] if scored else {}

    def _evaluate_logistics_proposal(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a sell proposal from logistics perspective."""
        destination = proposal.get("market", "domestic")
        sell_month = proposal.get("sell_month", 1)
        volume = proposal.get("volume_tonnes", self.logistics_context.volume_tonnes if self.logistics_context else 1000)
        
        # Calculate storage months needed
        harvest_calendar = get_harvest_calendar(
            self.logistics_context.crop if self.logistics_context else CropType.WHEAT,
            self.logistics_context.origin_country if self.logistics_context else Country.USA
        )
        harvest_end = harvest_calendar.harvest_end_month
        
        storage_months = max(0, sell_month - harvest_end)
        if storage_months > self.logistics_context.storage_capacity_months:
            storage_months = self.logistics_context.storage_capacity_months + 1
        
        cost = self._calculate_full_logistics_cost(destination, volume, storage_months)
        
        if not cost:
            return {"score": 0.0, "reasoning": "No logistics route available", "cost": None}
        
        total_cost = cost["total_cost_usd_per_tonne"]
        
        # Score: lower cost is better
        if total_cost <= 30:
            score = 0.9
        elif total_cost <= 50:
            score = 0.7
        elif total_cost <= 80:
            score = 0.5
        elif total_cost <= 120:
            score = 0.3
        else:
            score = 0.1
        
        # Penalize excessive storage
        if storage_months > self.logistics_context.storage_capacity_months:
            score *= 0.5
        
        reasoning = [
            f"Route: {self.logistics_context.origin_country.value} -> {destination}",
            f"Mode: {cost['mode']}, Distance: {cost['distance_km']} km",
            f"Transport: ${cost['transport_cost_usd_per_tonne']:.2f}/t, "
            f"Storage ({storage_months}m): ${cost['storage_cost_usd_per_tonne']:.2f}/t, "
            f"Handling: ${cost['handling_cost_usd_per_tonne']:.2f}/t",
            f"Total logistics cost: ${total_cost:.2f}/tonne",
            f"Transit time: {cost['transit_time_days']} days"
        ]
        
        counter_terms = None
        if score < 0.5:
            # Suggest closer market or different timing
            counter_terms = {
                "suggested_storage_months": min(storage_months, self.logistics_context.storage_capacity_months),
                "reason": "Reduce storage duration to lower costs"
            }
        
        return {
            "score": score,
            "cost": cost,
            "storage_months_needed": storage_months,
            "reasoning": "; ".join(reasoning),
            "counter_terms": counter_terms
        }

    def _generate_reasoning(self, market_costs: Dict, optimal: Dict) -> str:
        """Generate human-readable reasoning."""
        if not optimal:
            return "No viable logistics options found."
        
        parts = [
            f"Optimal market: {optimal['market']} via {optimal['details']['mode']} "
            f"(${optimal['total_cost']:.2f}/t total logistics cost, {optimal['transit_days']} days transit)."
        ]
        
        # Compare top 2
        if len(market_costs) > 1:
            sorted_markets = sorted(market_costs.items(), key=lambda x: x[1]['total_cost_usd_per_tonne'])
            alt = sorted_markets[1] if len(sorted_markets) > 1 else None
            if alt:
                diff = alt[1]['total_cost_usd_per_tonne'] - optimal['total_cost']
                parts.append(f"Alternative {alt[0]} costs ${diff:.2f}/t more.")
        
        return " ".join(parts)