"""
Market Agent - Analyzes price trends, demand/supply, and market conditions.
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy import stats
import logging

from .base import BaseAgent
from .models import (
    CropType, Country, MarketRegion, PricePoint, AgentMessage, 
    SellRecommendation
)

logger = logging.getLogger(__name__)


@dataclass
class MarketContext:
    """Context for the market agent."""
    crop: CropType
    country: Country
    target_markets: List[MarketRegion]
    analysis_years: int = 10


class MarketAgent(BaseAgent):
    """
    Market Agent - Responsible for:
    - Price trend analysis and forecasting
    - Seasonal pattern detection
    - Supply/demand balance assessment
    - Market opportunity identification
    - Price risk assessment
    """

    def __init__(self, agent_id: str, data_loader, config: Optional[Dict[str, Any]] = None):
        super().__init__(agent_id, "market", config)
        self.data_loader = data_loader
        self.market_context: Optional[MarketContext] = None
        self.price_history: List[PricePoint] = []
        self.seasonal_patterns: Dict[int, float] = {}  # month -> price multiplier

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
        
        if query_type == "price_forecast":
            forecast = self._forecast_prices(message.payload.get("horizon_months", 12))
            return AgentMessage(
                sender=self.state.agent_id,
                recipient=message.sender,
                message_type="response",
                payload={"query_type": "price_forecast", "forecast": forecast}
            )
        
        elif query_type == "seasonal_pattern":
            return AgentMessage(
                sender=self.state.agent_id,
                recipient=message.sender,
                message_type="response",
                payload={
                    "query_type": "seasonal_pattern",
                    "pattern": self.seasonal_patterns,
                    "peak_months": self._get_peak_price_months(),
                    "trough_months": self._get_trough_price_months()
                }
            )
        
        elif query_type == "market_analysis":
            analysis = self._analyze_market_conditions()
            return AgentMessage(
                sender=self.state.agent_id,
                recipient=message.sender,
                message_type="response",
                payload={"query_type": "market_analysis", "analysis": analysis}
            )
        
        elif query_type == "price_at_month":
            month = message.payload.get("month", 1)
            price = self._estimate_price_at_month(month)
            return AgentMessage(
                sender=self.state.agent_id,
                recipient=message.sender,
                message_type="response",
                payload={"query_type": "price_at_month", "month": month, "price_usd_per_tonne": price}
            )
        
        return AgentMessage(
            sender=self.state.agent_id,
            recipient=message.sender,
            message_type="response",
            payload={"error": f"Unknown query type: {query_type}"}
        )

    def _handle_proposal(self, message: AgentMessage) -> AgentMessage:
        """Evaluate a sell proposal from market perspective."""
        proposal = message.payload.get("proposal", {})
        evaluation = self._evaluate_market_proposal(proposal)
        
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
        return self._handle_proposal(message)

    def act(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Main action: analyze market conditions and generate price forecasts."""
        self.market_context = MarketContext(
            crop=CropType(context.get("crop", "wheat")),
            country=Country(context.get("country", "india")),
            target_markets=[MarketRegion(m) for m in context.get("target_markets", ["domestic", "export_asia"])],
            analysis_years=context.get("analysis_years", 10)
        )
        
        # Load historical price data
        self._load_price_history()
        
        # Analyze seasonal patterns
        self._analyze_seasonal_patterns()
        
        # Forecast prices
        forecast = self._forecast_prices(horizon_months=12)
        
        # Market conditions analysis
        market_analysis = self._analyze_market_conditions()
        
        # Identify optimal sell windows
        optimal_windows = self._identify_optimal_sell_windows()
        
        return {
            "agent": "market",
            "crop": self.market_context.crop.value,
            "country": self.market_context.country.value,
            "price_history_points": len(self.price_history),
            "seasonal_pattern": self.seasonal_patterns,
            "price_forecast": forecast,
            "market_analysis": market_analysis,
            "optimal_sell_windows": optimal_windows,
            "reasoning": self._generate_reasoning(forecast, market_analysis, optimal_windows)
        }

    def _load_price_history(self):
        """Load historical producer price data."""
        if not self.market_context:
            return
        
        crop_code = self._get_crop_code(self.market_context.crop)
        country_code = self._get_country_code(self.market_context.country)
        
        # Get recent years
        current_year = 2024
        years = list(range(current_year - self.market_context.analysis_years, current_year + 1))
        
        # Try to load USD/tonne price data first
        df = self.data_loader.get_price_data(
            item_codes=[crop_code],
            area_codes=[country_code],
            years=years,
            elements=[5532]  # USD/tonne
        )
        
        self.price_history = []
        self.price_index_history = {}
        
        if not df.empty:
            # USD price data available
            for _, row in df.iterrows():
                self.price_history.append(PricePoint(
                    year=int(row['Year']),
                    month=None,  # Annual data
                    price_usd_per_tonne=float(row['Value']),
                    source="FAOSTAT Producer Price (USD/tonne)"
                ))
        else:
            # Fallback: Use price index data to estimate prices
            logger.info(f"No USD price data for {self.market_context.crop.value} in {self.market_context.country.value}, using price index")
            
            # Load price index
            df_index = self.data_loader.get_price_data(
                item_codes=[crop_code],
                area_codes=[country_code],
                years=years,
                elements=[5539]  # Price Index (2014-2016=100)
            )
            
            if not df_index.empty:
                self.price_index_history = df_index.set_index('Year')['Value'].to_dict()
                
                # Estimate prices from price index using a base price
                # For India, use MSP as reference
                base_price_usd = self._get_base_price_for_country(crop_code, country_code)
                
                for _, row in df_index.iterrows():
                    year = int(row['Year'])
                    index_value = float(row['Value'])
                    # Estimate price: base_price * (index / 100)
                    estimated_price = base_price_usd * (index_value / 100.0)
                    self.price_history.append(PricePoint(
                        year=year,
                        month=None,
                        price_usd_per_tonne=estimated_price,
                        source="FAOSTAT Price Index (estimated from MSP base)"
                    ))
            else:
                logger.warning(f"No price data (USD or index) for {self.market_context.crop.value} in {self.market_context.country.value}")
        
        # Also load price index for trend analysis (if not already loaded)
        if not self.price_index_history:
            df_index = self.data_loader.get_price_data(
                item_codes=[crop_code],
                area_codes=[country_code],
                years=years,
                elements=[5539]  # Price Index
            )
            self.price_index_history = df_index.set_index('Year')['Value'].to_dict() if not df_index.empty else {}

        # FAOSTAT producer prices can sit far above what Indian farmers actually
        # receive. Rebase the series to the official MSP level while preserving
        # its year-on-year trend, so forecasts stay realistic for India.
        if country_code == 100 and self.price_history:
            from .models import INDIA_MSP_2026_27, CROP_CODE_TO_CROP, USD_TO_INR
            crop = CROP_CODE_TO_CROP.get(crop_code)
            if crop in INDIA_MSP_2026_27:
                msp_usd = INDIA_MSP_2026_27[crop] * 10 / USD_TO_INR  # ₹/q -> ₹/t -> USD/t
                recent = [p.price_usd_per_tonne for p in self.price_history[-5:]
                          if p.price_usd_per_tonne > 0]
                if recent:
                    scale = msp_usd / (sum(recent) / len(recent))
                    self.price_history = [
                        PricePoint(year=p.year, month=p.month,
                                   price_usd_per_tonne=p.price_usd_per_tonne * scale,
                                   price_lcu_per_tonne=p.price_lcu_per_tonne,
                                   price_index=p.price_index,
                                   source=p.source + " (rebased to MSP)")
                        for p in self.price_history
                    ]

        logger.info(f"Loaded {len(self.price_history)} price points for {self.market_context.crop.value} in {self.market_context.country.value}")

    def _get_base_price_for_country(self, crop_code: int, country_code: int) -> float:
        """Get base price (USD/tonne) for a crop/country combination.
        
        Uses MSP for India, otherwise uses a default reference price.
        """
        # India MSP (official 2026-27) converted ₹/quintal -> USD/tonne
        if country_code == 100:  # India
            from .models import INDIA_MSP_2026_27, CROP_CODE_TO_CROP, USD_TO_INR
            crop = CROP_CODE_TO_CROP.get(crop_code)
            if crop in INDIA_MSP_2026_27:
                return INDIA_MSP_2026_27[crop] * 10 / USD_TO_INR
            return 250.0
        
        # Default reference prices for other countries
        default_prices = {
            15: 250.0,   # Wheat
            27: 350.0,   # Rice
            56: 200.0,   # Maize
            236: 450.0,  # Soybeans
        }
        return default_prices.get(crop_code, 250.0)

    def _analyze_seasonal_patterns(self):
        """Analyze seasonal price patterns using harvest calendar and price data."""
        # Since FAOSTAT prices are annual, we infer seasonal patterns from:
        # 1. Harvest timing (prices typically drop at harvest for non-MSP countries)
        # 2. Global production cycles (opposite hemisphere)
        # 3. Historical price index volatility
        # 4. For India: MSP procurement provides price SUPPORT at harvest
        
        from .models import get_harvest_calendar, Country
        calendar = get_harvest_calendar(self.market_context.crop, self.market_context.country)
        
        harvest_peak = calendar.harvest_peak_months
        harvest_start = calendar.harvest_start_month
        harvest_end = calendar.harvest_end_month
        is_india = self.market_context.country == Country.INDIA
        
        # MSP procurement months for India (when government buys at MSP, supporting prices)
        msp_procurement_months = {
            15: [4, 5, 6],    # Wheat (Rabi): Apr-Jun
            27: [10, 11, 12], # Rice (Kharif): Oct-Dec
            56: [10, 11, 12], # Maize (Kharif): Oct-Dec
            236: [10, 11, 12], # Soybeans (Kharif): Oct-Dec
        }
        
        crop_code = self._get_crop_code(self.market_context.crop)
        msp_months = msp_procurement_months.get(crop_code, []) if is_india else []
        
        # Build seasonal pattern:
        # For India: MSP procurement months = STRONG prices (government buys at MSP)
        # For India harvest peak (if not MSP month): prices drop due to glut
        # For non-India: harvest = low prices, off-season = high prices
        pattern = {}
        for month in range(1, 13):
            is_msp_month = month in msp_months
            is_harvest_peak = month in harvest_peak
            is_harvest_period = False
            if harvest_end >= harvest_start:
                is_harvest_period = harvest_start <= month <= harvest_end
            else:
                # Year-wrap: e.g., start=10, end=1 means Oct-Jan
                is_harvest_period = month >= harvest_start or month <= harvest_end
            
            if is_india:
                if is_msp_month:
                    # MSP procurement month: government buys at MSP, STRONG prices
                    pattern[month] = 1.08  # Strong price support
                elif is_harvest_peak:
                    # Harvest peak but no MSP procurement: normal glut, prices drop
                    pattern[month] = 0.90
                elif is_harvest_period:
                    # Harvest period: prices slightly lower
                    pattern[month] = 0.95
                else:
                    # Off-season: higher prices due to storage costs and scarcity
                    pattern[month] = 1.05
            else:
                # Non-India: standard pattern
                if month in harvest_peak:
                    pattern[month] = 0.90
                elif harvest_start <= month <= harvest_end:
                    pattern[month] = 0.95
                elif month in [(harvest_start - 1) % 12 or 12, (harvest_end + 1) % 12 or 12]:
                    pattern[month] = 1.0
                else:
                    pattern[month] = 1.05
        
        # Adjust based on price index volatility if available
        idx_history = self.state.context.get('price_index_history', {})
        if idx_history:
            idx_values = list(idx_history.values())
            if len(idx_values) > 2:
                volatility = np.std(idx_values) / np.mean(idx_values)
                if volatility > 0.15:
                    for m in pattern:
                        if pattern[m] < 1.0:
                            pattern[m] *= 0.95
                        elif pattern[m] > 1.0:
                            pattern[m] *= 1.05
        
        self.seasonal_patterns = pattern

    def _forecast_prices(self, horizon_months: int = 12) -> List[Dict[str, Any]]:
        """Forecast prices for the next horizon_months."""
        if not self.price_history:
            return []
        
        from .models import Country
        is_india = self.market_context.country == Country.INDIA
        
        # MSP prices for India (USD/tonne) from the shared official table
        msp_prices = {}
        if is_india:
            from .models import INDIA_MSP_2026_27, CROP_CODE_TO_CROP, USD_TO_INR
            for code, crop in CROP_CODE_TO_CROP.items():
                if crop in INDIA_MSP_2026_27:
                    msp_prices[code] = INDIA_MSP_2026_27[crop] * 10 / USD_TO_INR
        
        # MSP procurement months for India
        msp_procurement_months = {
            15: [4, 5, 6],    # Wheat (Rabi): Apr-Jun
            27: [10, 11, 12], # Rice (Kharif): Oct-Dec
            56: [10, 11, 12], # Maize (Kharif): Oct-Dec
            236: [10, 11, 12], # Soybeans (Kharif): Oct-Dec
        }
        
        crop_code = self._get_crop_code(self.market_context.crop)
        msp_price = msp_prices.get(crop_code) if is_india else None
        msp_months = msp_procurement_months.get(crop_code, []) if is_india else []
        
        # Extract annual prices
        years = [p.year for p in self.price_history]
        prices = [p.price_usd_per_tonne for p in self.price_history]
        
        # Simple linear trend + seasonal adjustment
        if len(prices) < 3:
            # Not enough data, use last price with seasonal
            base_price = prices[-1] if prices else 200.0
            trend = 0.0
        else:
            # Fit trend
            slope, intercept, r_value, p_value, std_err = stats.linregress(years, prices)
            trend = slope
            base_price = slope * (max(years) + 1) + intercept
        
        # Generate monthly forecast
        forecast = []
        current_year = max(years) if years else 2024
        
        for i in range(horizon_months):
            month = (i % 12) + 1
            year = current_year + (i // 12)
            
            # Base price with trend
            trend_price = base_price + trend * (year - current_year + (month / 12))
            
            # Apply seasonal pattern
            seasonal_mult = self.seasonal_patterns.get(month, 1.0)
            forecast_price = trend_price * seasonal_mult
            
            # Apply MSP floor during procurement months for India (government guarantees minimum MSP)
            if msp_price is not None and month in msp_months:
                # During MSP procurement, government guarantees minimum MSP price
                forecast_price = max(forecast_price, msp_price)
            
            # Add confidence interval (wider for further months)
            uncertainty = 0.05 * (1 + i / 12)
            lower = forecast_price * (1 - uncertainty)
            upper = forecast_price * (1 + uncertainty)
            
            forecast.append({
                "year": year,
                "month": month,
                "price_usd_per_tonne": round(forecast_price, 2),
                "lower_bound": round(lower, 2),
                "upper_bound": round(upper, 2),
                "trend": "up" if trend > 0 else "down" if trend < 0 else "flat",
                "seasonal_factor": round(seasonal_mult, 3)
            })
        
        return forecast

    def _analyze_market_conditions(self) -> Dict[str, Any]:
        """Analyze current market conditions."""
        if not self.price_history:
            return {"status": "insufficient_data"}
        
        recent_prices = [p.price_usd_per_tonne for p in self.price_history[-5:]]
        current_price = recent_prices[-1]
        avg_price_5y = np.mean(recent_prices) if recent_prices else current_price
        avg_price_all = np.mean([p.price_usd_per_tonne for p in self.price_history])
        
        # Price vs historical
        vs_5y = (current_price - avg_price_5y) / avg_price_5y if avg_price_5y > 0 else 0
        vs_all = (current_price - avg_price_all) / avg_price_all if avg_price_all > 0 else 0
        
        # Volatility
        volatility = np.std(recent_prices) / avg_price_5y if avg_price_5y > 0 else 0
        
        # Global supply indicators (simplified - would use trade data in production)
        # For now, use production trends as proxy
        supply_trend = self.state.context.get('supply_trend', 'stable')
        
        return {
            "current_price_usd_per_tonne": round(current_price, 2),
            "vs_5y_avg_pct": round(vs_5y * 100, 1),
            "vs_all_time_avg_pct": round(vs_all * 100, 1),
            "volatility": round(volatility, 3),
            "supply_trend": supply_trend,
            "price_level": "high" if vs_all > 0.1 else "low" if vs_all < -0.1 else "average",
            "trend": "rising" if len(recent_prices) >= 2 and recent_prices[-1] > recent_prices[-2] else "falling"
        }

    def _identify_optimal_sell_windows(self) -> List[Dict[str, Any]]:
        """Identify optimal months to sell based on price forecasts and seasonal patterns."""
        forecast = self._forecast_prices(12)
        if not forecast:
            return []
        
        from .models import Country
        is_india = self.market_context.country == Country.INDIA
        
        # MSP procurement months for India (when government buys at MSP)
        msp_procurement_months = {
            15: [4, 5, 6],    # Wheat (Rabi): Apr-Jun
            27: [10, 11, 12], # Rice (Kharif): Oct-Dec
            56: [10, 11, 12], # Maize (Kharif): Oct-Dec
            236: [10, 11, 12], # Soybeans (Kharif): Oct-Dec
        }
        
        crop_code = self._get_crop_code(self.market_context.crop)
        msp_months = msp_procurement_months.get(crop_code, []) if is_india else []
        
        # Find local maxima in forecast
        windows = []
        for i, f in enumerate(forecast):
            is_peak = False
            if i == 0:
                is_peak = f["price_usd_per_tonne"] >= forecast[i+1]["price_usd_per_tonne"]
            elif i == len(forecast) - 1:
                is_peak = f["price_usd_per_tonne"] >= forecast[i-1]["price_usd_per_tonne"]
            else:
                is_peak = (f["price_usd_per_tonne"] >= forecast[i-1]["price_usd_per_tonne"] and
                          f["price_usd_per_tonne"] >= forecast[i+1]["price_usd_per_tonne"])
            
            if is_peak:
                windows.append({
                    "month": f["month"],
                    "year": f["year"],
                    "price_usd_per_tonne": f["price_usd_per_tonne"],
                    "confidence": 1.0 - (f["upper_bound"] - f["lower_bound"]) / (2 * f["price_usd_per_tonne"]),
                    "reason": "Forecasted local price maximum"
                })
        
        # Also add seasonal peaks
        seasonal_peaks = [m for m, mult in self.seasonal_patterns.items() if mult > 1.02]
        for month in seasonal_peaks:
            # Find corresponding forecast entry
            for f in forecast:
                if f["month"] == month:
                    windows.append({
                        "month": month,
                        "year": f["year"],
                        "price_usd_per_tonne": f["price_usd_per_tonne"],
                        "confidence": 0.7,
                        "reason": "Seasonal price strength (off-harvest period)"
                    })
                    break
        
        # Add MSP procurement windows for India (high priority)
        for month in msp_months:
            for f in forecast:
                if f["month"] == month:
                    # Use max of MSP and forecast price for MSP months (MSP is floor price)
                    msp_price = self._get_base_price_for_country(crop_code, 100)  # India
                    effective_price = max(msp_price, f["price_usd_per_tonne"])
                    windows.append({
                        "month": month,
                        "year": f["year"],
                        "price_usd_per_tonne": effective_price,  # MSP is floor price
                        "confidence": 0.95,  # High confidence for MSP window
                        "reason": "MSP procurement window (government price support)"
                    })
                    break
        
        # Deduplicate and sort by price
        seen = set()
        unique_windows = []
        for w in windows:
            key = (w["year"], w["month"])
            if key not in seen:
                seen.add(key)
                unique_windows.append(w)
        
        unique_windows.sort(key=lambda x: x["price_usd_per_tonne"], reverse=True)
        return unique_windows[:5]  # Top 5

    def _get_peak_price_months(self) -> List[int]:
        """Get months with highest seasonal prices."""
        sorted_months = sorted(self.seasonal_patterns.items(), key=lambda x: x[1], reverse=True)
        return [m for m, _ in sorted_months[:3]]

    def _get_trough_price_months(self) -> List[int]:
        """Get months with lowest seasonal prices."""
        sorted_months = sorted(self.seasonal_patterns.items(), key=lambda x: x[1])
        return [m for m, _ in sorted_months[:3]]

    def _estimate_price_at_month(self, month: int) -> float:
        """Estimate price for a specific month."""
        forecast = self._forecast_prices(12)
        for f in forecast:
            if f["month"] == month:
                return f["price_usd_per_tonne"]
        # Fallback to current price * seasonal
        if self.price_history:
            return self.price_history[-1].price_usd_per_tonne * self.seasonal_patterns.get(month, 1.0)
        return 200.0

    def _evaluate_market_proposal(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a sell proposal from market perspective."""
        from .models import Country
        is_india = self.market_context.country == Country.INDIA
        
        # MSP procurement months for India
        msp_procurement_months = {
            15: [4, 5, 6],    # Wheat (Rabi): Apr-Jun
            27: [10, 11, 12], # Rice (Kharif): Oct-Dec
            56: [10, 11, 12], # Maize (Kharif): Oct-Dec
            236: [10, 11, 12], # Soybeans (Kharif): Oct-Dec
        }
        
        sell_month = proposal.get("sell_month", 1)
        price = proposal.get("price_usd_per_tonne", 0)
        market = proposal.get("market", "domestic")
        
        crop_code = self._get_crop_code(self.market_context.crop)
        msp_months = msp_procurement_months.get(crop_code, []) if is_india else []
        is_msp_month = sell_month in msp_months
        
        # Get forecasted price for that month
        forecast_price = self._estimate_price_at_month(sell_month)
        
        # Score based on how close proposal price is to forecast
        if forecast_price > 0:
            price_ratio = price / forecast_price
            if 0.95 <= price_ratio <= 1.05:
                score = 0.9
            elif 0.9 <= price_ratio <= 1.1:
                score = 0.7
            elif 0.8 <= price_ratio <= 1.2:
                score = 0.5
            else:
                score = 0.3
        else:
            score = 0.5
        
        # Adjust for seasonal strength
        seasonal_mult = self.seasonal_patterns.get(sell_month, 1.0)
        if seasonal_mult > 1.02:
            score += 0.1
        elif seasonal_mult < 0.98:
            score -= 0.1
        
        # Bonus for MSP procurement months (guaranteed government procurement reduces risk)
        if is_msp_month:
            score += 0.15  # Significant bonus for guaranteed government procurement
        
        reasoning = [
            f"Forecasted price for month {sell_month}: ${forecast_price:.2f}/tonne",
            f"Proposed price: ${price:.2f}/tonne (ratio: {price/forecast_price:.2f})" if forecast_price > 0 else "No forecast available",
            f"Seasonal factor: {seasonal_mult:.2f}"
        ]
        
        if is_msp_month:
            reasoning.append(f"MSP procurement month: guaranteed government purchase at MSP")
        
        counter_terms = None
        if score < 0.6:
            # Suggest better month
            best_windows = self._identify_optimal_sell_windows()
            if best_windows:
                best = best_windows[0]
                counter_terms = {
                    "suggested_month": best["month"],
                    "suggested_price": best["price_usd_per_tonne"],
                    "reason": f"Better price window in month {best['month']}"
                }
        
        return {
            "score": min(1.0, max(0.0, score)),
            "forecast_price": forecast_price,
            "price_ratio": price / forecast_price if forecast_price > 0 else 1.0,
            "seasonal_strength": seasonal_mult,
            "reasoning": "; ".join(reasoning),
            "counter_terms": counter_terms
        }

    def _generate_reasoning(self, forecast: List, analysis: Dict, windows: List) -> str:
        """Generate human-readable reasoning."""
        if not forecast:
            return "Insufficient price data for analysis."
        
        trend = forecast[0]["trend"]
        current = analysis.get("current_price_usd_per_tonne", 0)
        vs_avg = analysis.get("vs_5y_avg_pct", 0)
        
        best_window = windows[0] if windows else {}
        
        parts = [
            f"Current {self.market_context.crop.value} price: ${current:.2f}/tonne "
            f"({vs_avg:+.1f}% vs 5-year avg). Trend: {trend}.",
            f"Seasonal pattern shows peak prices in months {self._get_peak_price_months()}, "
            f"trough at harvest months {self._get_trough_price_months()}.",
            f"Optimal sell window: Month {best_window.get('month', 'N/A')} "
            f"at ~${best_window.get('price_usd_per_tonne', 0):.2f}/tonne "
            f"(confidence: {best_window.get('confidence', 0):.0%})."
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