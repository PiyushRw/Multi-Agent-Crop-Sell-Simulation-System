"""
Farmer Agent - Decides production planning, harvest timing, and volume estimates.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import numpy as np
import logging

from .base import BaseAgent
from .models import (
    CropType, Country, ProductionData, HarvestCalendar, 
    AgentMessage, SellRecommendation, get_harvest_calendar
)

logger = logging.getLogger(__name__)


@dataclass
class FarmerContext:
    """Context for the farmer agent."""
    crop: CropType
    country: Country
    production_year: int
    farm_size_ha: float = 1000.0
    historical_yields: Optional[List[float]] = None
    risk_tolerance: str = "moderate"  # conservative, moderate, aggressive


class FarmerAgent(BaseAgent):
    """
    Farmer Agent - Responsible for:
    - Production planning and yield estimation
    - Harvest timing optimization
    - Volume forecasting
    - Risk assessment for production decisions
    """

    def __init__(self, agent_id: str, data_loader, config: Optional[Dict[str, Any]] = None):
        super().__init__(agent_id, "farmer", config)
        self.data_loader = data_loader
        self.farmer_context: Optional[FarmerContext] = None

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
        """Handle query messages from other agents."""
        query_type = message.payload.get("query_type")
        
        if query_type == "harvest_calendar":
            calendar = get_harvest_calendar(self.farmer_context.crop, self.farmer_context.country)
            return AgentMessage(
                sender=self.state.agent_id,
                recipient=message.sender,
                message_type="response",
                payload={
                    "query_type": "harvest_calendar",
                    "harvest_start": calendar.harvest_start_month,
                    "harvest_peak": calendar.harvest_peak_months,
                    "harvest_end": calendar.harvest_end_month,
                    "planting_months": calendar.planting_months
                }
            )
        
        elif query_type == "production_estimate":
            estimate = self._estimate_production()
            return AgentMessage(
                sender=self.state.agent_id,
                recipient=message.sender,
                message_type="response",
                payload={
                    "query_type": "production_estimate",
                    "estimated_volume_tonnes": estimate["volume"],
                    "yield_kg_per_ha": estimate["yield"],
                    "area_ha": estimate["area"],
                    "confidence": estimate["confidence"]
                }
            )
        
        elif query_type == "sell_timing_preference":
            prefs = self._get_sell_timing_preferences()
            return AgentMessage(
                sender=self.state.agent_id,
                recipient=message.sender,
                message_type="response",
                payload={
                    "query_type": "sell_timing_preference",
                    "preferred_months": prefs["preferred_months"],
                    "avoid_months": prefs["avoid_months"],
                    "storage_capacity_months": prefs["storage_capacity_months"],
                    "reasoning": prefs["reasoning"]
                }
            )
        
        return AgentMessage(
            sender=self.state.agent_id,
            recipient=message.sender,
            message_type="response",
            payload={"error": f"Unknown query type: {query_type}"}
        )

    def _handle_proposal(self, message: AgentMessage) -> AgentMessage:
        """Handle sell proposals from market/logistics agents."""
        proposal = message.payload.get("proposal", {})
        
        # Evaluate the proposal from farmer's perspective
        evaluation = self._evaluate_sell_proposal(proposal)
        
        return AgentMessage(
            sender=self.state.agent_id,
            recipient=message.sender,
            message_type="response",
            payload={
                "evaluation": evaluation,
                "accept": evaluation["score"] > 0.6,
                "counter_terms": evaluation.get("counter_terms"),
                "reasoning": evaluation["reasoning"]
            }
        )

    def _handle_counter_proposal(self, message: AgentMessage) -> AgentMessage:
        """Handle counter-proposals."""
        return self._handle_proposal(message)

    def act(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Main action: generate production plan and sell timing preferences."""
        self.farmer_context = FarmerContext(
            crop=CropType(context.get("crop", "wheat")),
            country=Country(context.get("country", "india")),
            production_year=context.get("production_year", 2024),
            farm_size_ha=context.get("farm_size_ha", 1000.0),
            risk_tolerance=context.get("risk_tolerance", "moderate")
        )
        
        # Load historical data
        self._load_historical_data()
        
        # Generate production estimate
        production_estimate = self._estimate_production()
        
        # Get harvest calendar
        calendar = get_harvest_calendar(self.farmer_context.crop, self.farmer_context.country)
        
        # Get sell timing preferences
        timing_prefs = self._get_sell_timing_preferences()
        
        # Risk assessment
        risk_assessment = self._assess_production_risks()
        
        return {
            "agent": "farmer",
            "crop": self.farmer_context.crop.value,
            "country": self.farmer_context.country.value,
            "production_year": self.farmer_context.production_year,
            "production_estimate": production_estimate,
            "harvest_calendar": {
                "planting_months": calendar.planting_months,
                "harvest_start": calendar.harvest_start_month,
                "harvest_peak": calendar.harvest_peak_months,
                "harvest_end": calendar.harvest_end_month
            },
            "sell_timing_preferences": timing_prefs,
            "risk_assessment": risk_assessment,
            "reasoning": self._generate_reasoning(production_estimate, timing_prefs, risk_assessment)
        }

    def _load_historical_data(self):
        """Load historical production data for the crop/country."""
        if not self.farmer_context:
            return
            
        crop_code = self._get_crop_code(self.farmer_context.crop)
        country_code = self._get_country_code(self.farmer_context.country)
        years = list(range(self.farmer_context.production_year - 10, self.farmer_context.production_year))
        
        df = self.data_loader.get_production_data(
            item_codes=[crop_code],
            area_codes=[country_code],
            years=years,
            elements=[5312, 5510, 5513, 5412]
        )
        
        if not df.empty:
            # Extract yields
            yield_data = df[df['Element Code'] == 5412]
            self.farmer_context.historical_yields = yield_data['Value'].tolist()
            
            # Extract production
            prod_data = df[df['Element Code'].isin([5510, 5513])]
            self.state.context['historical_production'] = prod_data.groupby('Year')['Value'].sum().to_dict()
            
            # Extract area
            area_data = df[df['Element Code'] == 5312]
            self.state.context['historical_area'] = area_data.set_index('Year')['Value'].to_dict()

    def _estimate_production(self) -> Dict[str, Any]:
        """Estimate production for the current year."""
        if not self.farmer_context or not self.farmer_context.historical_yields:
            return {
                "volume": 0.0,
                "yield": 0.0,
                "area": self.farmer_context.farm_size_ha if self.farmer_context else 0.0,
                "confidence": 0.3
            }
        
        yields = np.array(self.farmer_context.historical_yields)
        
        # Use recent trend (last 5 years) for prediction
        recent_yields = yields[-5:] if len(yields) >= 5 else yields
        predicted_yield = float(np.mean(recent_yields))
        yield_std = float(np.std(recent_yields)) if len(recent_yields) > 1 else predicted_yield * 0.15
        
        # Area is the FARMER's own plot. National harvested area is kept only as
        # context — using it here reported the whole country's harvest as one farm.
        area = self.farmer_context.farm_size_ha
        
        volume = area * predicted_yield / 1000.0  # Convert kg to tonnes
        
        # Confidence based on yield stability
        cv = yield_std / predicted_yield if predicted_yield > 0 else 1.0
        confidence = max(0.3, min(0.9, 1.0 - cv))
        
        return {
            "volume": volume,
            "yield": predicted_yield,
            "area": area,
            "yield_std": yield_std,
            "confidence": confidence
        }

    def _get_sell_timing_preferences(self) -> Dict[str, Any]:
        """Determine farmer's preferred sell timing based on harvest and storage."""
        if not self.farmer_context:
            return {}
        
        calendar = get_harvest_calendar(self.farmer_context.crop, self.farmer_context.country)
        
        # Farmer prefers to sell around harvest (cash flow) but can store
        harvest_peak = calendar.harvest_peak_months
        harvest_end = calendar.harvest_end_month
        
        # Storage capacity based on crop type
        storage_months = {
            CropType.WHEAT: 12,
            CropType.MAIZE: 12,
            CropType.RICE: 6,
            CropType.SOYBEANS: 10,
            CropType.BARLEY: 12,
        }.get(self.farmer_context.crop, 6)
        
        # Handle year wrap-around for harvest_end < harvest_peak[0]
        # (e.g., harvest ends in January but peaks in Nov/Dec)
        if harvest_end < harvest_peak[0]:
            # Harvest spans year boundary - preferred months are peak through end of year + start of next year
            preferred = list(range(harvest_peak[0], 13)) + list(range(1, harvest_end + 1))
        else:
            # Normal case: harvest peak through harvest end + storage
            preferred = list(range(harvest_peak[0], min(12, harvest_end + storage_months) + 1))
        
        # Apply storage capacity limit
        if len(preferred) > storage_months + len(harvest_peak):
            preferred = preferred[:storage_months + len(harvest_peak)]
        
        # Avoid months: planting season and just before harvest (old crop depletion)
        avoid = calendar.planting_months + [m for m in range(1, harvest_peak[0])]
        
        # Format preferred months for display
        if preferred:
            pref_str = f"{preferred[0]}-{preferred[-1]}" if len(preferred) > 1 else str(preferred[0])
        else:
            pref_str = "N/A"
        
        return {
            "preferred_months": preferred,
            "avoid_months": list(set(avoid)),
            "storage_capacity_months": storage_months,
            "reasoning": f"Harvest peaks in months {harvest_peak}. Can store for {storage_months} months. "
                         f"Prefer selling {pref_str}. Avoid {avoid} (planting/pre-harvest)."
        }

    def _assess_production_risks(self) -> Dict[str, Any]:
        """Assess risks for the current production year."""
        if not self.farmer_context or not self.farmer_context.historical_yields:
            return {"level": "unknown", "factors": []}
        
        yields = np.array(self.farmer_context.historical_yields)
        cv = np.std(yields) / np.mean(yields) if np.mean(yields) > 0 else 1.0
        
        # Recent trend
        recent = yields[-3:] if len(yields) >= 3 else yields
        trend = np.polyfit(range(len(recent)), recent, 1)[0] if len(recent) > 1 else 0
        
        risk_factors = []
        if cv > 0.2:
            risk_factors.append(f"High yield variability (CV={cv:.1%})")
        if trend < -50:
            risk_factors.append("Declining yield trend")
        
        # Climate risk (simplified)
        risk_factors.append("Weather uncertainty during growing season")
        risk_factors.append("Input cost volatility (fertilizer, fuel)")
        
        risk_level = "high" if cv > 0.25 or trend < -100 else "moderate" if cv > 0.15 else "low"
        
        return {
            "level": risk_level,
            "yield_cv": float(cv),
            "yield_trend": float(trend),
            "factors": risk_factors
        }

    def _evaluate_sell_proposal(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a sell proposal from market/logistics perspective."""
        sell_month = proposal.get("sell_month", 1)
        market = proposal.get("market", "domestic")
        price = proposal.get("price_usd_per_tonne", 0)
        volume = proposal.get("volume_tonnes", 0)
        
        # Check if month aligns with harvest (handle year-wrap)
        calendar = get_harvest_calendar(self.farmer_context.crop, self.farmer_context.country)
        if calendar.harvest_end_month >= calendar.harvest_start_month:
            in_harvest_window = calendar.harvest_start_month <= sell_month <= calendar.harvest_end_month
        else:
            # Year-wrap: e.g., start=11, end=1 means Nov-Jan
            in_harvest_window = sell_month >= calendar.harvest_start_month or sell_month <= calendar.harvest_end_month
        in_harvest_window = in_harvest_window or sell_month in calendar.harvest_peak_months
        
        # Check storage implications (handle year-wrap)
        prefs = self._get_sell_timing_preferences()
        storage_needed = 0
        harvest_end = calendar.harvest_end_month
        if harvest_end >= calendar.harvest_start_month:
            # Normal case: no year-wrap
            if sell_month > harvest_end:
                storage_needed = sell_month - harvest_end
        else:
            # Year-wrap: harvest ends in Jan/Feb
            if sell_month > harvest_end and sell_month < calendar.harvest_start_month:
                storage_needed = sell_month - harvest_end
        
        if storage_needed > prefs["storage_capacity_months"]:
            storage_needed = prefs["storage_capacity_months"] + 1  # Exceeds capacity
        
        # Score the proposal
        score = 0.5  # Base
        if in_harvest_window:
            score += 0.2
        if storage_needed == 0:
            score += 0.1
        elif storage_needed <= prefs["storage_capacity_months"]:
            score += 0.05
        else:
            score -= 0.2
        
        # Price reasonableness (compare to historical)
        hist_prices = self.state.context.get('historical_prices', [])
        if hist_prices:
            avg_price = np.mean(hist_prices)
            if price >= avg_price * 0.9:
                score += 0.15
            elif price >= avg_price * 0.8:
                score += 0.05
            else:
                score -= 0.1
        
        reasoning = []
        if in_harvest_window:
            reasoning.append("Aligns with harvest timing - minimal storage needed")
        else:
            reasoning.append(f"Requires {storage_needed} months storage")
        reasoning.append(f"Price ${price:.2f}/tonne")
        
        counter_terms = None
        if score < 0.6 and storage_needed > prefs["storage_capacity_months"]:
            counter_terms = {
                "suggested_month": calendar.harvest_peak_months[0],
                "reason": "Exceeds storage capacity, prefer harvest-time sale"
            }
        
        return {
            "score": min(1.0, max(0.0, score)),
            "in_harvest_window": in_harvest_window,
            "storage_months_needed": storage_needed,
            "reasoning": "; ".join(reasoning),
            "counter_terms": counter_terms
        }

    def _generate_reasoning(self, prod_estimate: Dict, timing_prefs: Dict, risks: Dict) -> str:
        """Generate human-readable reasoning."""
        parts = [
            f"Farmer projects {prod_estimate['volume']:,.0f} tonnes of {self.farmer_context.crop.value} "
            f"from {prod_estimate['area']:,.0f} ha at {prod_estimate['yield']:,.0f} kg/ha "
            f"(confidence: {prod_estimate['confidence']:.0%}).",
            f"Harvest peaks in months {timing_prefs['preferred_months'][0]}-{timing_prefs['preferred_months'][-1]}. "
            f"Can store for {timing_prefs['storage_capacity_months']} months.",
            f"Production risk: {risks['level']}. Key concerns: {'; '.join(risks['factors'][:2])}."
        ]
        return " ".join(parts)

    def _get_crop_code(self, crop: CropType) -> int:
        crop_codes = {
            CropType.WHEAT: 15, CropType.MAIZE: 56, CropType.RICE: 27,
            CropType.SOYBEANS: 236, CropType.BARLEY: 44, CropType.SORGHUM: 83
        }
        return crop_codes.get(crop, 15)

    def _get_country_code(self, country: Country) -> int:
        country_codes = {
            Country.USA: 231, Country.BRAZIL: 21, Country.INDIA: 100,
            Country.CHINA: 351, Country.ARGENTINA: 10, Country.RUSSIA: 185,
            Country.UKRAINE: 230, Country.CANADA: 39, Country.AUSTRALIA: 14,
            Country.FRANCE: 75, Country.GERMANY: 81
        }
        return country_codes.get(country, 231)