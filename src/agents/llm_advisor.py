#!/usr/bin/env python
"""
Optional LLM Enhancement Layer for Crop Sell Advisory Chatbot
Supports local (Ollama) and remote (OpenAI, Anthropic) models.
Default: DISABLED - chatbot works perfectly without this.
"""

import os
import json
import time
import requests
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class LLMConfig:
    """Configuration for LLM provider."""
    provider: str  # "ollama", "openai", "anthropic", "openrouter"
    model: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 500
    enabled: bool = False


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate response from prompt."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available."""
        pass


class OllamaProvider(LLMProvider):
    """Local Ollama provider (recommended for privacy)."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.base_url = config.base_url or "http://localhost:11434"
    
    def is_available(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                return any(self.config.model in m.get("name", "") for m in models)
        except Exception:
            pass
        return False
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens
            }
        }
        if system_prompt:
            payload["system"] = system_prompt
        
        resp = requests.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=60
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.api_key = config.api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = config.base_url or "https://api.openai.com/v1"
    
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens
        }
        
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.api_key = config.api_key or os.getenv("ANTHROPIC_API_KEY")
        self.base_url = config.base_url or "https://api.anthropic.com/v1"
    
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        payload = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "messages": [{"role": "user", "content": prompt}]
        }
        if system_prompt:
            payload["system"] = system_prompt
        
        resp = requests.post(
            f"{self.base_url}/messages",
            headers=headers,
            json=payload,
            timeout=60
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"].strip()


class OpenRouterProvider(LLMProvider):
    """OpenRouter API provider (access to many models)."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.api_key = config.api_key or os.getenv("OPENROUTER_API_KEY")
        self.base_url = config.base_url or "https://openrouter.ai/api/v1"
    
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/crop-sell-simulation",
            "X-Title": "Crop Sell Advisor"
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens
        }
        
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


class GeminiProvider(LLMProvider):
    """Google Gemini API provider (free tier available)."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.api_key = config.api_key or os.getenv("GEMINI_API_KEY")
        self.base_url = config.base_url or "https://generativelanguage.googleapis.com/v1beta"
    
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        # Combine system prompt and user prompt for Gemini
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        payload = {
            "contents": [{
                "parts": [{"text": full_prompt}]
            }],
            "generationConfig": {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_tokens,
                "topP": 0.95,
                "topK": 40
            }
        }
        
        # Gemini 3.x spends most of the output budget on hidden thinking, which
        # truncates short replies mid-word. Disable it for those models.
        if self.config.model.startswith("gemini-3."):
            payload["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0}

        headers = {
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}/models/{self.config.model}:generateContent?key={self.api_key}"

        # Brief retry for transient 503 under load
        for attempt in range(2):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=45)
                resp.raise_for_status()
                break
            except requests.exceptions.HTTPError as e:
                if attempt == 0 and e.response is not None and e.response.status_code in (429, 503):
                    time.sleep(1)
                    continue
                raise

        result = resp.json()
        candidates = result.get("candidates", [])
        if candidates:
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if parts:
                return parts[0].get("text", "").strip()
        return ""


PROVIDER_MAP = {
    "ollama": OllamaProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "openrouter": OpenRouterProvider,
    "gemini": GeminiProvider,
}


def create_llm_provider(config: LLMConfig) -> Optional[LLMProvider]:
    """Factory function to create LLM provider."""
    if not config.enabled:
        return None
    
    provider_class = PROVIDER_MAP.get(config.provider.lower())
    if not provider_class:
        raise ValueError(f"Unknown provider: {config.provider}")
    
    provider = provider_class(config)
    if not provider.is_available():
        print(f"⚠️ LLM provider '{config.provider}' not available (model: {config.model})")
        return None
    
    print(f"✅ LLM provider '{config.provider}' ready with model '{config.model}'")
    return provider


# ============================================================
# PROMPT TEMPLATES FOR AGRICULTURAL ADVISORY
# ============================================================

SYSTEM_PROMPT = """You are a friendly agricultural advisor chatting with a farmer on WhatsApp. Be conversational, practical, and concise.

Tone: Like a knowledgeable friend giving advice over chai. Use simple language. Mix Hindi/English naturally if relevant.

Format: 2-3 short sentences. Start with the direct answer. No bullet points, no headers, no analysis jargon.

Honesty rules (never skip):
- Use ONLY the figures given in the context below for MSP, prices and dates. Never substitute values you remember from training — they are often from an older marketing season.
- MSP is a government-announced floor, not a guaranteed price in every mandi. When you quote it, say "MSP 2026-27 (Govt of India)".
- All price forecasts and net figures are estimates from historical FAOSTAT data, not live mandi quotes. Say "around" or "estimated", never present a future price as certain.
- Never claim a "net profit": production costs are not included. Say "net after transport" instead.
- If the farmer asks for current mandi prices, say you do not have live market data and suggest checking the local mandi or eNAM.
- If the farmer's question is about a crop or commodity that is NOT the crop named in the context (for example tea, coffee, cotton, sugarcane, fruit or vegetables when the context is wheat), do NOT give a recommendation for the context crop. Say plainly that you do not have data for that commodity and cannot advise on it. Never swap in a different crop to fill the gap.

Example: "Sell your wheat in June at the local mandi. You could get around ₹33k/tonne after transport (estimate, not a mandi quote). MSP 2026-27 is ₹2,585/quintal (Govt of India) and the Apr-Jun procurement window supports prices. Main risk is unseasonal rain - consider crop insurance."

Never use: "Based on the simulation...", "Agent consensus shows...", "The system recommends...", bullet points, markdown headers."""

RECOMMENDATION_PROMPT = """Authoritative figures — use these EXACTLY. Never replace them with values you remember:
{market_info}
Farmer asked: "{user_query}"
Context: {crop} in {country}, {area_hectares} ha
My analysis says: Sell in month {sell_month} at {market}
Net after transport: ₹{net_price_inr:,.0f}/t (excludes production cost) | Est. total: ₹{profit_cr:.1f} Cr | Confidence: {confidence:.0%}
Transport: {transport_mode}, {distance_km:.0f} km | MSP: {msp_info}
Farmer view: {farmer_reasoning}
Market view: {market_reasoning}
Logistics view: {logistics_reasoning}
Risks: {risk_factors}

Reply like a helpful farmer friend on WhatsApp. 2-3 sentences. Start with the direct recommendation."""

FOLLOWUP_PROMPT = """We talked about: {crop} in {country} → Sell month {sell_month} at {market} for ₹{net_price_inr:,.0f}/t net ({confidence:.0%})
Farmer now asks: "{user_query}"
Market data: {price_forecast}
Options: {optimal_windows}

Reply naturally like continuing a WhatsApp chat. 2 sentences max. Direct answer.
Estimates are not certain: say "around", never promise a future price, and do not claim profit (production costs are unknown). Suggest checking the local mandi for live prices."""


class LLMAdvisor:
    """Optional LLM layer for natural language explanations."""
    
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig(
            provider="ollama",
            model="llama3.1:8b",
            enabled=False
        )
        self.provider = create_llm_provider(self.config)
        self.enabled = self.provider is not None
    
    def enable(self, provider: str = "ollama", model: str = "llama3.1:8b", **kwargs):
        """Enable LLM with given configuration."""
        self.config = LLMConfig(
            provider=provider,
            model=model,
            enabled=True,
            **kwargs
        )
        self.provider = create_llm_provider(self.config)
        self.enabled = self.provider is not None
        return self.enabled
    
    def disable(self):
        """Disable LLM - fall back to template-based responses."""
        self.enabled = False
        self.provider = None
    
    def explain_recommendation(self, rec, user_query: str = "", params: Dict = None) -> str:
        """Generate farmer-friendly explanation of recommendation."""
        if not self.enabled or not self.provider:
            return self._template_response(rec, params)
        
        try:
            # Build MSP info with source and season (official, not a mandi quote)
            msp_info = "Not applicable"
            if rec.msp_price_inr_per_quintal > 0:
                from .models import MSP_SEASON, MSP_SOURCE
                msp_info = (f"MSP {MSP_SEASON} ({MSP_SOURCE}): "
                            f"₹{rec.msp_price_inr_per_quintal:,.0f}/quintal, "
                            f"procurement months {rec.msp_procurement_months}")
            
            # Build alternatives text
            alt_text = "None"
            if rec.alternatives:
                alt_lines = []
                for alt in rec.alternatives[:3]:
                    alt_lines.append(
                        f"  Month {alt['month']}: ₹{alt.get('net_price_inr', alt.get('net_price', 0)):,.0f}/t net "
                        f"({alt.get('reason', 'Alternative')})"
                    )
                alt_text = "\n".join(alt_lines)
            
            # Build risk factors
            risk_text = "; ".join(rec.risk_factors) if rec.risk_factors else "None identified"
            
            # Month name
            month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            month_name = month_names[rec.recommended_sell_month - 1] if rec.recommended_sell_month > 0 else "N/A"
            
            prompt = RECOMMENDATION_PROMPT.format(
                market_info=msp_info,
                user_query=user_query or "When and where should I sell my crop?",
                crop=rec.crop.value if hasattr(rec.crop, 'value') else str(rec.crop),
                country=rec.country.value if hasattr(rec.country, 'value') else str(rec.country),
                area_hectares=params.get('area_hectares', 1000) if params else 1000,
                sell_month=rec.recommended_sell_month,
                month_name=month_name,
                market=rec.recommended_market.value.replace('_', ' ').title() if hasattr(rec.recommended_market, 'value') else str(rec.recommended_market),
                price_inr=rec.expected_price_inr_per_tonne,
                logistics_inr=rec.logistics_cost_inr_per_tonne,
                net_price_inr=rec.net_price_inr_per_tonne,
                revenue_inr=rec.total_revenue_inr,
                profit_inr=rec.net_profit_inr,
                profit_cr=rec.net_profit_inr/1e7,
                confidence=rec.confidence_score,
                transport_mode=rec.transport_mode,
                distance_km=rec.distance_km,
                transit_days=rec.transit_days,
                storage_months=rec.storage_months,
                farmer_reasoning=rec.farmer_reasoning or "N/A",
                market_reasoning=rec.market_reasoning or "N/A",
                logistics_reasoning=rec.logistics_reasoning or "N/A",
                msp_info=msp_info,
                risk_factors=risk_text,
                alternatives=alt_text
            )
            
            response = self.provider.generate(prompt, SYSTEM_PROMPT)
            return response.strip()
            
        except Exception as e:
            print(f"LLM error: {e}, falling back to template")
            return self._template_response(rec, params)
    
    def answer_followup(self, rec, user_query: str, params: Dict = None) -> str:
        """Answer follow-up questions from farmer."""
        from .models import USD_TO_INR
        if not self.enabled or not self.provider:
            return self._template_followup(rec, user_query)
        
        try:
            # Build price forecast summary
            forecast_text = "Not available"
            if rec.price_forecast:
                forecast_lines = []
                for f in rec.price_forecast[:6]:
                    forecast_lines.append(
                        f"  Month {f['month']}: ₹{f.get('price_inr_per_tonne', f.get('price_usd_per_tonne', 0)*USD_TO_INR):,.0f}/t "
                        f"(trend: {f.get('trend', 'flat')})"
                    )
                forecast_text = "\n".join(forecast_lines)
            
            windows_text = "Not available"
            if rec.optimal_windows:
                window_lines = []
                for w in rec.optimal_windows[:3]:
                    window_lines.append(
                        f"  Month {w['month']}: ₹{w.get('price_inr_per_tonne', w.get('price_usd_per_tonne', 0)*USD_TO_INR):,.0f}/t "
                        f"(conf: {w.get('confidence', 0):.0%})"
                    )
                windows_text = "\n".join(window_lines)
            
            prompt = FOLLOWUP_PROMPT.format(
                crop=rec.crop.value if hasattr(rec.crop, 'value') else str(rec.crop),
                country=rec.country.value if hasattr(rec.country, 'value') else str(rec.country),
                sell_month=rec.recommended_sell_month,
                market=rec.recommended_market.value.replace('_', ' ').title() if hasattr(rec.recommended_market, 'value') else str(rec.recommended_market),
                net_price_inr=rec.net_price_inr_per_tonne,
                confidence=rec.confidence_score,
                user_query=user_query,
                price_forecast=forecast_text,
                optimal_windows=windows_text
            )
            
            response = self.provider.generate(prompt, SYSTEM_PROMPT)
            return response.strip()
            
        except Exception as e:
            print(f"LLM followup error: {e}, falling back to template")
            return self._template_followup(rec, user_query)
    
    def _template_response(self, rec, params: Dict = None) -> str:
        """Fallback template-based response (current implementation)."""
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        month_name = month_names[rec.recommended_sell_month - 1] if rec.recommended_sell_month > 0 else "N/A"
        market_name = rec.recommended_market.value.replace('_', ' ').title() if hasattr(rec.recommended_market, 'value') else str(rec.recommended_market)
        
        response = f"""
**🎯 My Recommendation:**

**📅 When to Sell:** **{month_name}** (Month {rec.recommended_sell_month})
**🏪 Where to Sell:** **{market_name}**
**💰 Estimated Price:** **₹{rec.expected_price_inr_per_tonne:,.0f}/tonne** (model estimate)
**🚚 Logistics Cost:** **₹{rec.logistics_cost_inr_per_tonne:,.0f}/tonne**
**💵 Net after transport:** **₹{rec.net_price_inr_per_tonne:,.0f}/tonne** (excludes production cost)
**📊 Est. Total Revenue:** **₹{rec.total_revenue_inr:,.0f}**
**💚 Est. Net after transport:** **₹{rec.net_profit_inr:,.0f}** (not profit — production costs excluded)
**🎯 Confidence: {rec.confidence_score:.0%}**

**🤖 Agent Consensus:**
"""
        for agent, reasoning in rec.reasoning_trace.items():
            response += f"- **{agent.title()}**: {reasoning}\n"
        
        if rec.risk_factors:
            response += "\n⚠️ **Key Risks to Watch:**\n"
            for risk in rec.risk_factors:
                response += f"- {risk}\n"
        
        if rec.alternatives:
            response += "\n🔄 **Alternative Options:**\n"
            for alt in rec.alternatives[:3]:
                response += f"- Month {alt['month']} ({month_names[alt['month']-1]}): ₹{alt.get('net_price_inr', alt.get('net_price', 0)):,.0f}/t, {alt.get('confidence', 0):.0%} conf\n"

        if rec.msp_price_inr_per_quintal > 0:
            from .models import MSP_SEASON, MSP_SOURCE
            response += (f"\n📌 MSP {MSP_SEASON}: ₹{rec.msp_price_inr_per_quintal:,.0f}/quintal "
                         f"({MSP_SOURCE}) — a government floor, not a guaranteed mandi price. ")
        response += ("⚠️ Prices are estimates from historical FAOSTAT data, not live mandi quotes. "
                     "Check your local mandi or eNAM before selling.\n")

        return response
    
    def _template_followup(self, rec, user_query: str) -> str:
        """Template fallback for follow-up questions."""
        return f"Based on the simulation for {rec.crop.value}, I recommend selling in month {rec.recommended_sell_month} at {rec.recommended_market.value} for a net price of ₹{rec.net_price_inr_per_tonne:,.0f}/tonne. For your specific question: '{user_query}', please refer to the detailed analysis tabs above."


# ============================================================
# CONVENIENCE FUNCTIONS FOR CHATBOT INTEGRATION
# ============================================================

def get_llm_advisor(
    provider: str = "ollama",
    model: str = "llama3.1:8b",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    enabled: bool = True
) -> LLMAdvisor:
    """Get configured LLM advisor instance."""
    config = LLMConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        enabled=enabled
    )
    return LLMAdvisor(config)


def quick_setup_ollama(model: str = "llama3.1:8b") -> LLMAdvisor:
    """Quick setup for local Ollama (recommended)."""
    return get_llm_advisor(provider="ollama", model=model, enabled=True)


def quick_setup_openai(model: str = "gpt-4o-mini", api_key: Optional[str] = None) -> LLMAdvisor:
    """Quick setup for OpenAI API."""
    return get_llm_advisor(provider="openai", model=model, api_key=api_key, enabled=True)


def quick_setup_openrouter(model: str = "meta-llama/llama-3.1-8b-instruct:free", api_key: Optional[str] = None) -> LLMAdvisor:
    """Quick setup for OpenRouter (free models available)."""
    return get_llm_advisor(provider="openrouter", model=model, api_key=api_key, enabled=True)


def quick_setup_gemini(model: str = "gemini-3.6-flash", api_key: Optional[str] = None) -> LLMAdvisor:
    """Quick setup for Google Gemini (free tier: 15 RPM, 1M tokens/day).
    
    Get free API key at: https://aistudio.google.com/apikey
    """
    return get_llm_advisor(provider="gemini", model=model, api_key=api_key, enabled=True)


# Example usage:
if __name__ == "__main__":
    # Test with Ollama (requires: ollama serve && ollama pull llama3.1:8b)
    advisor = quick_setup_ollama("llama3.1:8b")
    if advisor.enabled:
        print("LLM Advisor ready!")
    else:
        print("Ollama not available. Install: ollama serve && ollama pull llama3.1:8b")
        print("Or use: quick_setup_openai('gpt-4o-mini', api_key='...')")
        print("Or use: quick_setup_gemini('gemini-3.6-flash', api_key='...')")