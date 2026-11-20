#!/usr/bin/env python
"""
LLM-Enhanced Agent Wrappers
Uses LLM to enhance agent decision-making for production, pricing, and logistics.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import json

try:
    from src.agents.llm_advisor import LLMAdvisor, quick_setup_gemini
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

try:
    from src.agents.models import USD_TO_INR
except ImportError:
    USD_TO_INR = 93.5


@dataclass
class LLMConfig:
    """Configuration for LLM-enhanced agents."""
    enabled: bool = False
    provider: str = "gemini"
    model: str = "gemini-3.6-flash"
    api_key: Optional[str] = None


class LLMFarmerAgent:
    """LLM-enhanced Farmer Agent for production and harvest decisions."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.advisor = None
        if config.enabled and LLM_AVAILABLE:
            if config.provider == "gemini":
                self.advisor = quick_setup_gemini(model=config.model, api_key=config.api_key)
    
    def estimate_production(self, crop: str, country: str, area_hectares: float, 
                           historical_yields: List[float], historical_area: List[float],
                           weather_conditions: str = "normal") -> Dict[str, Any]:
        """Use LLM to estimate production with context."""
        if not self.advisor or not self.advisor.enabled:
            return self._fallback_production(area_hectares, historical_yields)
        
        prompt = f"""You are an agricultural economist. Estimate production for:
Crop: {crop} in {country}
Area: {area_hectares:,.0f} hectares
Historical yields (last 5 years): {[f'{y:.0f}' for y in historical_yields[-5:]]}
Historical area (last 5 years): {[f'{a:,.0f}' for a in historical_area[-5:]]}
Current weather: {weather_conditions}

Respond with JSON only:
{{
  "estimated_yield_kg_per_ha": number,
  "estimated_area_ha": number, 
  "estimated_volume_tonnes": number,
  "confidence": 0-1,
  "reasoning": "brief explanation"
}}"""
        
        try:
            response = self.advisor.provider.generate(prompt)
            return json.loads(response)
        except Exception:
            return self._fallback_production(area_hectares, historical_yields)
    
    def assess_harvest_timing(self, crop: str, country: str, current_month: int,
                             harvest_calendar: Dict) -> Dict[str, Any]:
        """Use LLM to assess optimal harvest/sell timing."""
        if not self.advisor or not self.advisor.enabled:
            return self._fallback_timing(harvest_calendar)
        
        prompt = f"""You are a farmer advisor. Assess harvest/sell timing:
Crop: {crop} in {country}
Current month: {current_month}
Harvest calendar: planting={harvest_calendar.get('planting_months', [])}, 
  harvest_start={harvest_calendar.get('harvest_start_month')}, 
  harvest_peak={harvest_calendar.get('harvest_peak_months', [])}, 
  harvest_end={harvest_calendar.get('harvest_end_month')}
Storage capacity months: {harvest_calendar.get('storage_capacity_months', 6)}

Current month relative to harvest: {'pre-harvest' if current_month < harvest_calendar.get('harvest_start_month', 1) else 'harvest' if current_month <= harvest_calendar.get('harvest_end_month', 12) else 'post-harvest'}

Respond with JSON:
{{
  "preferred_sell_months": [month_numbers],
  "avoid_months": [month_numbers],
  "storage_recommendation": "sell_now/store_X_months",
  "reasoning": "brief explanation",
  "risk_level": "low/medium/high"
}}"""
        
        try:
            response = self.advisor.provider.generate(prompt)
            return json.loads(response)
        except Exception:
            return self._fallback_timing(harvest_calendar)
    
    def _fallback_production(self, area_hectares: float, historical_yields: List[float]) -> Dict[str, Any]:
        avg_yield = sum(historical_yields[-5:]) / min(5, len(historical_yields)) if historical_yields else 3000
        return {
            "estimated_yield_kg_per_ha": avg_yield,
            "estimated_area_ha": area_hectares,
            "estimated_volume_tonnes": area_hectares * avg_yield / 1000,
            "confidence": 0.7,
            "reasoning": "Based on 5-year historical average"
        }
    
    def _fallback_timing(self, harvest_calendar: Dict) -> Dict[str, Any]:
        peak = harvest_calendar.get('harvest_peak_months', [1])
        return {
            "preferred_sell_months": peak,
            "avoid_months": harvest_calendar.get('planting_months', []),
            "storage_recommendation": "sell_at_harvest",
            "reasoning": "Sell at harvest peak",
            "risk_level": "medium"
        }


class LLMMarketAgent:
    """LLM-enhanced Market Agent for price forecasting and window optimization."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.advisor = None
        if config.enabled and LLM_AVAILABLE:
            if config.provider == "gemini":
                self.advisor = quick_setup_gemini(model=config.model, api_key=config.api_key)
    
    def forecast_prices(self, crop: str, country: str, historical_prices: List[Dict],
                       msp_price: float, current_month: int) -> Dict[str, Any]:
        """Use LLM to forecast prices with market context."""
        if not self.advisor or not self.advisor.enabled:
            return self._fallback_forecast(historical_prices, msp_price)
        
        recent = historical_prices[-10:] if len(historical_prices) > 10 else historical_prices
        prompt = f"""You are a commodity market analyst. Forecast prices:
Crop: {crop} in {country}
Historical prices (last 10 years): {[f"{p.get('year', 'N/A')}: ₹{p.get('price_inr_per_tonne', p.get('price_usd_per_tonne', 0)*USD_TO_INR):,.0f}/t" for p in recent]}
MSP (Minimum Support Price): ₹{msp_price:,.0f}/quintal = ₹{msp_price*10:,.0f}/tonne
Current month: {current_month}

Consider: MSP procurement window support, seasonal patterns, global trends, stock levels.

Respond with JSON:
{{
  "forecast_12_months": [
    {{"month": 1, "price_inr_per_tonne": number, "confidence": 0-1, "trend": "up/down/flat"}},
    ...
  ],
  "optimal_sell_months": [month_numbers],
  "price_trend": "up/down/flat",
  "reasoning": "brief explanation"
}}"""
        
        try:
            response = self.advisor.provider.generate(prompt)
            return json.loads(response)
        except Exception:
            return self._fallback_forecast(historical_prices, msp_price)
    
    def _fallback_forecast(self, historical_prices: List[Dict], msp_price: float) -> Dict[str, Any]:
        avg_price = sum(p.get('price_inr_per_tonne', p.get('price_usd_per_tonne', 0)*USD_TO_INR) for p in historical_prices[-5:]) / min(5, len(historical_prices)) if historical_prices else msp_price * 10
        return {
            "forecast_12_months": [
                {"month": m, "price_inr_per_tonne": avg_price, "confidence": 0.6, "trend": "flat"} 
                for m in range(1, 13)
            ],
            "optimal_sell_months": [6, 11, 12],
            "price_trend": "flat",
            "reasoning": "Based on 5-year average"
        }


class LLMLogisticsAgent:
    """LLM-enhanced Logistics Agent for route and mode optimization."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.advisor = None
        if config.enabled and LLM_AVAILABLE:
            if config.provider == "gemini":
                self.advisor = quick_setup_gemini(model=config.model, api_key=config.api_key)
    
    def optimize_route(self, origin: str, destination: str, volume_tonnes: float,
                      crop: str, available_modes: List[str], distances: Dict[str, float],
                      storage_months: int) -> Dict[str, Any]:
        """Use LLM to optimize logistics route and mode."""
        if not self.advisor or not self.advisor.enabled:
            return self._fallback_route(available_modes, distances)
        
        prompt = f"""You are a logistics optimizer. Find best route:
Crop: {crop} ({'perishable' if crop in ['rice', 'soybeans'] else 'durable'})
Volume: {volume_tonnes:,.0f} tonnes
Origin: {origin}
Destination: {destination}
Available modes: {available_modes}
Distances (km): {distances}
Storage needed: {storage_months} months

Mode costs (₹/tonne-km): Truck=8, Rail=4, Barge=2.5, Ocean=1.5, Container=3
Fixed costs per shipment: Truck=5000, Rail=20000, Barge=15000, Ocean=50000, Container=30000
Storage cost: ₹250-300/t/month (diminishing 100%/90%/80%)
Handling: ₹200/t, Insurance: 0.2% cargo value/month

Respond with JSON:
{{
  "optimal_mode": "mode_name",
  "route": "origin -> destination",
  "total_cost_inr_per_tonne": number,
  "cost_breakdown": {{"transport": n, "storage": n, "handling": n, "insurance": n}},
  "transit_days": number,
  "storage_months": number,
  "reasoning": "brief explanation"
}}"""
        
        try:
            response = self.advisor.provider.generate(prompt)
            return json.loads(response)
        except Exception:
            return self._fallback_route(available_modes, distances)
    
    def _fallback_route(self, available_modes: List[str], distances: Dict[str, float]) -> Dict[str, Any]:
        mode = "rail" if "rail" in available_modes else available_modes[0]
        dist = distances.get(mode, 1000)
        rates = {"truck": 8, "rail": 4, "barge": 2.5, "ocean": 1.5, "container": 3}
        return {
            "optimal_mode": mode,
            "route": "optimized",
            "total_cost_inr_per_tonne": dist * rates.get(mode, 4) + 5000,
            "cost_breakdown": {"transport": dist * rates.get(mode, 4), "storage": 0, "handling": 200, "insurance": 500},
            "transit_days": max(1, dist // 300),
            "storage_months": 0,
            "reasoning": "Lowest cost mode available"
        }


class LLMCoordinator:
    """LLM-enhanced Coordinator for multi-agent negotiation."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.advisor = None
        if config.enabled and LLM_AVAILABLE:
            if config.provider == "gemini":
                self.advisor = quick_setup_gemini(model=config.model, api_key=config.api_key)
    
    def negotiate(self, farmer_proposal: Dict, market_proposal: Dict, logistics_proposal: Dict,
                 round_num: int, max_rounds: int = 3) -> Dict[str, Any]:
        """Use LLM to mediate multi-agent negotiation."""
        if not self.advisor or not self.advisor.enabled:
            return self._fallback_negotiate(farmer_proposal, market_proposal, logistics_proposal)
        
        prompt = f"""You are a negotiation mediator for crop selling. Three agents propose:

FARMER: {json.dumps(farmer_proposal, default=str)}
MARKET: {json.dumps(market_proposal, default=str)}  
LOGISTICS: {json.dumps(logistics_proposal, default_str)}

Round: {round_num}/{max_rounds}
Acceptance thresholds: Farmer>0.6, Market>0.6, Logistics>0.5

Find consensus. If impossible, propose compromise.

Respond with JSON:
{{
  "consensus": true/false,
  "final_recommendation": {{
    "sell_month": number,
    "market": "market_name",
    "price_inr_per_tonne": number,
    "volume_tonnes": number
  }},
  "adjustments": {{
    "farmer": {{"suggested_month": n, "suggested_storage": n}},
    "market": {{"suggested_price": n}},
    "logistics": {{"suggested_mode": "mode", "suggested_storage": n}}
  }},
  "reasoning": "brief explanation"
}}"""
        
        try:
            response = self.advisor.provider.generate(prompt)
            return json.loads(response)
        except Exception:
            return self._fallback_negotiate(farmer_proposal, market_proposal, logistics_proposal)
    
    def _fallback_negotiate(self, farmer: Dict, market: Dict, logistics: Dict) -> Dict[str, Any]:
        return {
            "consensus": True,
            "final_recommendation": {
                "sell_month": market.get("optimal_month", 6),
                "market": logistics.get("optimal_market", "domestic"),
                "price_inr_per_tonne": market.get("price", 25000),
                "volume_tonnes": farmer.get("volume", 1000)
            },
            "adjustments": {},
            "reasoning": "Default consensus"
        }


def create_llm_agents(config: LLMConfig):
    """Factory function to create all LLM-enhanced agents."""
    return {
        "farmer": LLMFarmerAgent(config),
        "market": LLMMarketAgent(config),
        "logistics": LLMLogisticsAgent(config),
        "coordinator": LLMCoordinator(config)
    }