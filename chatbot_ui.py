#!/usr/bin/env python
"""
Crop Sell Advisory Chatbot - Professional Chat UI
A Streamlit-based chatbot interface with streaming, history, and proper UX.
"""

import streamlit as st
import sys
import os
import time
import uuid
from pathlib import Path
from datetime import datetime
from typing import Generator, Optional

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.simulation.orchestrator import run_simulation
from src.agents.models import CropType, Country, MarketRegion
from src.query_guard import detect_supported_crop, detect_unsupported_commodity

# Try to import LLM advisor (optional)
try:
    from src.agents.llm_advisor import LLMAdvisor, quick_setup_gemini, quick_setup_ollama, quick_setup_openai, quick_setup_openrouter
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

# ============================================================
# PAGE CONFIG & STYLING
# ============================================================
st.set_page_config(
    page_title="🌾 Crop Sell Advisor",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': "Multi-Agent Crop Sell Advisory System"
    }
)

# Custom CSS for proper chat UI
st.markdown("""
<style>
    /* Hide Streamlit default elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}
    
    /* Chat container */
    .chat-container {
        height: calc(100vh - 200px);
        overflow-y: auto;
        padding: 1rem;
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }
    
    /* Message bubbles */
    .message {
        max-width: 85%;
        padding: 0.875rem 1.25rem;
        border-radius: 1.25rem;
        animation: fadeIn 0.3s ease-out;
        line-height: 1.6;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .message-user {
        align-self: flex-end;
        background: linear-gradient(135deg, #2E7D32 0%, #4CAF50 100%);
        color: white;
        border-bottom-right-radius: 0.375rem;
    }
    
    .message-assistant {
        align-self: flex-start;
        background: #F5F5F5;
        color: #2C3E50;
        border-bottom-left-radius: 0.375rem;
        border: 1px solid #E0E0E0;
    }
    
    .message-system {
        align-self: center;
        background: #FFF3E0;
        color: #E65100;
        font-size: 0.875rem;
        padding: 0.5rem 1rem;
        border-radius: 1rem;
        max-width: 100%;
    }
    
    /* Typing indicator */
    .typing-indicator {
        display: flex;
        gap: 4px;
        padding: 0.5rem 1rem;
    }
    
    .typing-dot {
        width: 8px;
        height: 8px;
        background: #9E9E9E;
        border-radius: 50%;
        animation: typing 1.4s infinite ease-in-out;
    }
    
    .typing-dot:nth-child(2) { animation-delay: 0.2s; }
    .typing-dot:nth-child(3) { animation-delay: 0.4s; }
    
    @keyframes typing {
        0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
        30% { transform: translateY(-6px); opacity: 1; }
    }
    
    /* Sidebar chat history */
    .chat-session-item {
        padding: 0.75rem 1rem;
        border-radius: 0.75rem;
        margin: 0.25rem 0;
        cursor: pointer;
        transition: all 0.2s;
        border: 1px solid transparent;
    }
    
    .chat-session-item:hover {
        background: #F1F8E9;
        border-color: #C8E6C9;
    }
    
    .chat-session-item.active {
        background: #E8F5E9;
        border-color: #4CAF50;
        font-weight: 600;
    }
    
    .chat-session-title {
        font-size: 0.875rem;
        color: #2E7D32;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis.
    }
    
    .chat-session-time {
        font-size: 0.75rem;
        color: #78909C;
        margin-top: 0.25rem.
    }
    
    /* Quick action buttons */
    .quick-action {
        display: inline-block;
        padding: 0.5rem 1rem;
        margin: 0.25rem;
        background: #E8F5E9;
        color: #2E7D32;
        border: 1px solid #C8E6C9;
        border-radius: 2rem;
        font-size: 0.875rem;
        cursor: pointer;
        transition: all 0.2s.
    }
    
    .quick-action:hover {
        background: #2E7D32;
        color: white;
        border-color: #2E7D32.
    }
    
    /* Input area */
    .stChatInputContainer {
        background: white;
        border-top: 1px solid #E0E0E0;
        padding: 1rem.
    }
    
    /* Status badges */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.375rem;
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
        font-size: 0.75rem;
        font-weight: 600.
    }
    
    .status-connected { background: #E8F5E9; color: #2E7D32. }
    .status-disconnected { background: #FFEBEE; color: #C62828. }
    .status-processing { background: #FFF3E0; color: #E65100. }
    
    /* Recommendation card */
    .recommendation-card {
        background: linear-gradient(135deg, #E8F5E9 0%, #F1F8E9 100%);
        border: 2px solid #4CAF50;
        border-radius: 1rem;
        padding: 1.5rem;
        margin: 1rem 0.
    }
    
    .recommendation-row {
        display: flex;
        justify-content: space-between;
        padding: 0.5rem 0;
        border-bottom: 1px solid #C8E6C9.
    }
    
    .recommendation-row:last-child { border-bottom: none; }
    
    .rec-label { color: #558B2F; font-weight: 500. }
    .rec-value { color: #1B5E20; font-weight: 700. }
    
    /* Agent badges */
    .agent-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.375rem;
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
        font-size: 0.75rem;
        font-weight: 600;
        margin: 0.25rem.
    }
    
    .agent-farmer { background: #E8F5E9; color: #2E7D32. }
    .agent-market { background: #E3F2FD; color: #1565C0. }
    .agent-logistics { background: #FFF3E0; color: #E65100. }
    .agent-coordinator { background: #F3E5F5; color: #7B1FA2. }
    
    /* Risk tags */
    .risk-tag {
        display: inline-block;
        padding: 0.25rem 0.625rem;
        border-radius: 0.5rem;
        font-size: 0.75rem;
        margin: 0.25rem.
    }
    
    .risk-high { background: #FFEBEE; color: #C62828. }
    .risk-medium { background: #FFF3E0; color: #E65100. }
    .risk-low { background: #E8F5E9; color: #2E7D32. }
    
    /* Mobile responsive */
    @media (max-width: 768px) {
        .message { max-width: 95%; }
        .chat-container { padding: 0.5rem; }
    }
    
    /* Quick action buttons in sidebar */
    .stButton > button[kind="secondary"] {
        background: #E8F5E9 !important;
        color: #2E7D32 !important;
        border: 1px solid #C8E6C9 !important;
        border-radius: 2rem !important;
        font-size: 0.875rem !important;
        padding: 0.5rem 1rem !important;
        margin: 0.25rem 0 !important;
        width: 100% !important;
        text-align: left !important;
        transition: all 0.2s !important.
    }
    
    .stButton > button[kind="secondary"]:hover {
        background: #2E7D32 !important;
        color: white !important;
        border-color: #2E7D32 !important.
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# SESSION STATE INITIALIZATION
# ============================================================
if "messages" not in st.session_state:
    st.session_state.messages = []

if "recommendation" not in st.session_state:
    st.session_state.recommendation = None

if "simulation_params" not in st.session_state:
    st.session_state.simulation_params = {
        "crop": "wheat",
        "country": "india",
        "year": 2026,
        "area_hectares": 1000,
        "risk_tolerance": "moderate"
    }

if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = []

if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = str(uuid.uuid4())

if "use_llm" not in st.session_state:
    st.session_state.use_llm = False

if "llm_provider" not in st.session_state:
    st.session_state.llm_provider = "gemini"

if "typing" not in st.session_state:
    st.session_state.typing = False

# Crop and country mappings
CROP_DISPLAY = {
    "wheat": "🌾 Wheat", "rice_paddy": "🌾 Rice (Paddy)", "maize": "🌽 Maize",
    "soybeans": "🫘 Soybeans", "barley": "🌾 Barley", "sorghum": "🌾 Sorghum",
}

COUNTRY_DISPLAY = {
    "india": "🇮🇳 India", "usa": "🇺🇸 USA", "brazil": "🇧🇷 Brazil",
    "china": "🇨🇳 China", "argentina": "🇦🇷 Argentina", "russia": "🇷🇺 Russia",
    "ukraine": "🇺🇦 Ukraine", "canada": "🇨🇦 Canada", "australia": "🇦🇺 Australia",
    "france": "🇫🇷 France", "germany": "🇩🇪 Germany",
}

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# ============================================================
# HELPER FUNCTIONS
# ============================================================
def format_inr(amount: float) -> str:
    if amount >= 1e7:
        return f"₹{amount/1e7:.2f} Cr"
    elif amount >= 1e5:
        return f"₹{amount/1e5:.2f} Lakh"
    else:
        return f"₹{amount:,.0f}"

def run_crop_simulation(crop: str, country: str, year: int, area_hectares: float, risk: str, llm_config: Optional["LLMConfig"] = None):
    try:
        rec = run_simulation(crop, country, year, area_hectares, "data", llm_config)
        return rec, None
    except Exception as e:
        return None, str(e)

def parse_natural_language(query: str) -> dict:
    query_lower = query.lower()
    params = st.session_state.simulation_params.copy()
    
    crop = detect_supported_crop(query_lower)
    if crop:
        params["crop"] = crop
    
    country_keywords = {
        "india": ["india", "भारत", "bharat", "punjab", "haryana", "up", "madhya pradesh"],
        "usa": ["usa", "america", "united states"],
        "brazil": ["brazil", "ब्राजील"],
        "china": ["china", "चीन"],
        "argentina": ["argentina", "अर्जेंटीना"],
    }
    for country, keywords in country_keywords.items():
        if any(k in query_lower for k in keywords):
            params["country"] = country
            break
    
    import re
    area_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:hectare|ha|acre|बीघा)', query_lower)
    if area_match:
        area = float(area_match.group(1))
        if "acre" in query_lower:
            area = area * 0.4047
        params["area_hectares"] = area
    
    year_match = re.search(r'(20\d{2})', query)
    if year_match:
        params["year"] = int(year_match.group(1))
    
    if any(w in query_lower for w in ["high risk", "aggressive", "risky"]):
        params["risk_tolerance"] = "high"
    elif any(w in query_lower for w in ["low risk", "conservative", "safe"]):
        params["risk_tolerance"] = "low"
    elif any(w in query_lower for w in ["moderate", "medium", "balanced"]):
        params["risk_tolerance"] = "moderate"
    
    return params

def generate_advice_response(rec, params: dict) -> str:
    crop_name = CROP_DISPLAY.get(params["crop"], params["crop"])
    country_name = COUNTRY_DISPLAY.get(params["country"], params["country"])
    month_name = MONTH_NAMES[rec.recommended_sell_month - 1] if rec.recommended_sell_month > 0 else "N/A"
    market_name = rec.recommended_market.value.replace("_", " ").title() if hasattr(rec.recommended_market, 'value') else str(rec.recommended_market)
    
    # Ultra-concise chat response
    response = f"""**Sell {crop_name} in {month_name} at {market_name}**
💰 **₹{rec.net_price_inr_per_tonne:,.0f}/t after transport** (est. ₹{rec.expected_price_inr_per_tonne:,.0f} - ₹{rec.logistics_cost_inr_per_tonne:,.0f} logistics; production cost excluded)
📊 **Est. net after transport: ₹{rec.net_profit_inr/1e7:.1f} Cr** | **Confidence: {rec.confidence_score:.0%}**
🚛 {rec.transport_mode.title()}, {rec.distance_km:,.0f} km, {rec.transit_days} days"""

    # One-line risk summary
    if rec.risk_factors:
        response += f"\n⚠️ {', '.join(rec.risk_factors[:2])}"

    # One alternative
    if rec.alternatives:
        alt = rec.alternatives[0]
        alt_month = MONTH_NAMES[alt['month']-1] if alt['month'] > 0 else "N/A"
        response += f"\n🔄 Or {alt_month} at ₹{alt.get('net_price_inr', alt.get('net_price', 0)):,.0f}/t (estimate)"

    # Data provenance and uncertainty — never present estimates as certain
    if rec.msp_price_inr_per_quintal > 0:
        from src.agents.models import MSP_SEASON, MSP_SOURCE
        response += (f"\n📌 MSP {MSP_SEASON}: ₹{rec.msp_price_inr_per_quintal:,.0f}/q "
                     f"({MSP_SOURCE}) — a floor, not a guaranteed mandi price.")
    response += "\nℹ️ Estimates from historical FAOSTAT data, not live mandi prices. Verify at your local mandi / eNAM."

    return response

def generate_llm_response(rec, params: dict, user_query: str) -> str:
    # MSP is a factual lookup — answer from authoritative app data, never from the
    # LLM's training memory (which contains older seasons' figures).
    if "msp" in user_query.lower() or "minimum support price" in user_query.lower():
        from src.agents.models import MSP_SEASON, MSP_SOURCE
        if rec.msp_price_inr_per_quintal <= 0:
            return "MSP is an India-specific government scheme — no MSP applies to this selection."
        crop_label = CROP_DISPLAY.get(params.get("crop"), params.get("crop", "crop"))
        months = ", ".join(MONTH_NAMES[m - 1] for m in rec.msp_procurement_months
                           if 1 <= m <= 12)
        return (f"**MSP for {crop_label} ({MSP_SEASON}): ₹{rec.msp_price_inr_per_quintal:,.0f}/quintal**\n"
                f"📌 Source: {MSP_SOURCE}. This is the government-announced floor, "
                f"not a guaranteed price in every mandi.\n"
                f"🗓️ Procurement months: {months or 'not specified'}\n"
                f"ℹ️ Check current mandi rates at eNAM or your local market before selling.")

    if not LLM_AVAILABLE:
        return generate_advice_response(rec, params)
    
    try:
        use_llm = st.session_state.get("use_llm", False)
        if not use_llm:
            return generate_advice_response(rec, params)
        
        llm_provider = st.session_state.get("llm_provider", "gemini")
        
        if llm_provider == "gemini":
            api_key = st.session_state.get("gemini_api_key")
            model = st.session_state.get("gemini_model", "gemini-3.6-flash")
            if not api_key:
                return generate_advice_response(rec, params) + "\n\n⚠️ *Gemini API key not provided.*"
            from src.agents.llm_advisor import quick_setup_gemini
            advisor = quick_setup_gemini(model=model, api_key=api_key)
        elif llm_provider == "ollama":
            model = st.session_state.get("ollama_model", "llama3.1:8b")
            from src.agents.llm_advisor import quick_setup_ollama
            advisor = quick_setup_ollama(model=model)
        elif llm_provider == "openai":
            api_key = st.session_state.get("openai_api_key")
            model = st.session_state.get("openai_model", "gpt-4o-mini")
            if not api_key:
                return generate_advice_response(rec, params) + "\n\n⚠️ *OpenAI API key not provided.*"
            from src.agents.llm_advisor import quick_setup_openai
            advisor = quick_setup_openai(model=model, api_key=api_key)
        elif llm_provider == "openrouter":
            api_key = st.session_state.get("openrouter_api_key")
            model = st.session_state.get("openrouter_model", "meta-llama/llama-3.1-8b-instruct:free")
            if not api_key:
                return generate_advice_response(rec, params) + "\n\n⚠️ *OpenRouter API key not provided.*"
            from src.agents.llm_advisor import quick_setup_openrouter
            advisor = quick_setup_openrouter(model=model, api_key=api_key)
        else:
            return generate_advice_response(rec, params)
        
        if not advisor.enabled:
            return generate_advice_response(rec, params) + f"\n\n⚠️ *{llm_provider} not available.*"
        
        is_followup = len(st.session_state.messages) > 1
        
        if is_followup:
            response = advisor.answer_followup(rec, user_query, params)
        else:
            response = advisor.explain_recommendation(rec, user_query, params)
        
        return response
        
    except Exception as e:
        return generate_advice_response(rec, params) + f"\n\n⚠️ *LLM error: {e}*"

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    # Logo & Title
    st.markdown("""
    <div style="text-align: center; padding: 1rem 0;">
        <h1 style="margin: 0; font-size: 1.5rem;">🌾 Crop Sell Advisor</h1>
        <p style="color: #78909C; margin: 0.5rem 0 0;">Multi-Agent AI for Farmers</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    # Chat History / Sessions
    st.markdown("### 💬 Chat History")
    
    if st.button("➕ New Chat", use_container_width=True, type="primary"):
        # Save current session
        if st.session_state.messages:
            st.session_state.chat_sessions.append({
                "id": st.session_state.current_session_id,
                "title": st.session_state.messages[0]["content"][:50] if st.session_state.messages else "New Chat",
                "time": datetime.now().strftime("%H:%M"),
                "messages": st.session_state.messages.copy(),
                "recommendation": st.session_state.recommendation,
                "params": st.session_state.simulation_params.copy()
            })
        
        # Reset for new chat
        st.session_state.current_session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.recommendation = None
        st.rerun()
    
    # Show previous sessions
    for session in reversed(st.session_state.chat_sessions[-10:]):
        is_active = session["id"] == st.session_state.current_session_id
        col1, col2 = st.columns([0.85, 0.15])
        with col1:
            if st.button(
                f"{'🟢 ' if is_active else '⚪ '}{session['title']}",
                key=f"session_{session['id']}",
                use_container_width=True
            ):
                st.session_state.current_session_id = session["id"]
                st.session_state.messages = session["messages"]
                st.session_state.recommendation = session["recommendation"]
                st.session_state.simulation_params = session["params"]
                st.rerun()
        with col2:
            if not is_active:
                if st.button("🗑️", key=f"delete_{session['id']}", help="Delete session"):
                    st.session_state.chat_sessions.remove(session)
                    st.rerun()
    
    st.divider()
    
    # Simulation Parameters
    st.markdown("### ⚙️ Parameters")
    
    crop = st.selectbox(
        "Crop",
        options=list(CROP_DISPLAY.keys()),
        format_func=lambda x: CROP_DISPLAY[x],
        index=list(CROP_DISPLAY.keys()).index(st.session_state.simulation_params["crop"])
    )
    
    country = st.selectbox(
        "Country",
        options=list(COUNTRY_DISPLAY.keys()),
        format_func=lambda x: COUNTRY_DISPLAY[x],
        index=list(COUNTRY_DISPLAY.keys()).index(st.session_state.simulation_params["country"])
    )
    
    col1, col2 = st.columns(2)
    with col1:
        year = st.number_input("Year", 2020, 2030, st.session_state.simulation_params["year"])
    with col2:
        area = st.number_input("Area (ha)", 1.0, 10000.0, float(st.session_state.simulation_params["area_hectares"]), step=10.0)
    
    risk = st.selectbox(
        "Risk",
        options=["low", "moderate", "high"],
        index=["low", "moderate", "high"].index(st.session_state.simulation_params["risk_tolerance"])
    )
    
    st.session_state.simulation_params = {
        "crop": crop, "country": country, "year": year,
        "area_hectares": area, "risk_tolerance": risk
    }
    
    st.divider()
    
    # LLM Settings
    st.markdown("### 🤖 AI Enhancement")
    use_llm = st.checkbox("Enable LLM", value=True)  # Default ON
    st.session_state.use_llm = use_llm
    
    if use_llm and LLM_AVAILABLE:
        llm_provider = st.selectbox(
            "Provider",
            options=["gemini", "ollama", "openai", "openrouter"],
            format_func=lambda x: {
                "gemini": "🌟 Gemini (Free: 15 RPM, 1M/day)",
                "ollama": "🦙 Ollama (Local, free)",
                "openai": "🤖 OpenAI (Paid)",
                "openrouter": "🔀 OpenRouter (Free models)"
            }[x],
            index=["gemini", "ollama", "openai", "openrouter"].index(st.session_state.llm_provider)
        )
        st.session_state.llm_provider = llm_provider
        
        if llm_provider == "gemini":
            # Auto-load from .env if available
            env_key = os.getenv("GEMINI_API_KEY", "")
            gemini_api_key = st.text_input("Gemini API Key", type="password", 
                help="Get free key at: https://aistudio.google.com/apikey (auto-loaded from .env)",
                value=st.session_state.get("gemini_api_key", env_key))
            if gemini_api_key:
                st.session_state.gemini_api_key = gemini_api_key
            if env_key and not st.session_state.get("gemini_api_key"):
                st.session_state.gemini_api_key = env_key
                st.caption("✅ Loaded from .env file")
            gemini_model = st.selectbox("Model", ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-lite-latest", "gemini-3.1-flash-lite"])
            st.session_state.gemini_model = gemini_model
            
        elif llm_provider == "ollama":
            ollama_model = st.selectbox("Model", ["llama3.1:8b", "llama3.1:70b", "mistral:7b", "gemma2:9b"])
            st.session_state.ollama_model = ollama_model
            
        elif llm_provider == "openai":
            env_key = os.getenv("OPENAI_API_KEY", "")
            openai_api_key = st.text_input("OpenAI API Key", type="password",
                value=st.session_state.get("openai_api_key", env_key))
            if env_key and not st.session_state.get("openai_api_key"):
                st.session_state.openai_api_key = env_key
                st.caption("✅ Loaded from .env file")
            openai_model = st.selectbox("Model", ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"])
            st.session_state.openai_model = openai_model
            
        elif llm_provider == "openrouter":
            env_key = os.getenv("OPENROUTER_API_KEY", "")
            openrouter_api_key = st.text_input("OpenRouter API Key", type="password",
                value=st.session_state.get("openrouter_api_key", env_key))
            if env_key and not st.session_state.get("openrouter_api_key"):
                st.session_state.openrouter_api_key = env_key
                st.caption("✅ Loaded from .env file")
            openrouter_model = st.selectbox("Model", ["meta-llama/llama-3.1-8b-instruct:free", "google/gemma-2-9b-it:free", "mistralai/mistral-7b-instruct:free"])
            st.session_state.openrouter_model = openrouter_model
    elif use_llm and not LLM_AVAILABLE:
        st.warning("LLM module not available. Restart app after adding src/agents/llm_advisor.py")
    
    st.divider()
    
    # Quick Actions
    st.markdown("### ⚡ Quick Questions")
    quick_questions = [
        "When should I sell wheat in Punjab?",
        "Best market for 500 ha rice in India?",
        "Should I store maize or sell now?",
        "Transport cost for wheat to Delhi?",
        "What's the MSP for wheat this year?"
    ]
    
    for q in quick_questions:
        if st.button(q, key=f"quick_{q}", use_container_width=True):
            st.session_state.pending_query = q
            st.rerun()

# ============================================================
# MAIN CHAT INTERFACE
# ============================================================

# Header
st.markdown("""
<div style="background: linear-gradient(135deg, #2E7D32 0%, #4CAF50 100%); 
            padding: 1.5rem; border-radius: 1rem; margin-bottom: 1rem; color: white;">
    <h1 style="margin: 0; font-size: 1.75rem;">🌾 Crop Sell Advisor</h1>
    <p style="margin: 0.5rem 0 0; opacity: 0.9;">Ask me when, where, and how to sell your crops</p>
</div>
""", unsafe_allow_html=True)

# Status bar
col1, col2, col3, col4 = st.columns(4)
with col1:
    status_class = "status-connected" if st.session_state.recommendation else "status-disconnected"
    status_text = "Ready" if st.session_state.recommendation else "No Data"
    st.markdown(f'<span class="status-badge {status_class}">📊 {status_text}</span>', unsafe_allow_html=True)
with col2:
    if st.session_state.recommendation:
        crop_name = CROP_DISPLAY.get(st.session_state.simulation_params["crop"], "")
        st.markdown(f'<span class="status-badge status-connected">🌾 {crop_name}</span>', unsafe_allow_html=True)
with col3:
    if st.session_state.use_llm and LLM_AVAILABLE:
        provider_names = {"gemini": "🌟 Gemini", "ollama": "🦙 Ollama", "openai": "🤖 OpenAI", "openrouter": "🔀 OpenRouter"}
        st.markdown(f'<span class="status-badge status-connected">{provider_names.get(st.session_state.llm_provider, "AI")} On</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-badge status-disconnected">🤖 AI Off</span>', unsafe_allow_html=True)
with col4:
    if st.session_state.recommendation:
        conf = st.session_state.recommendation.confidence_score
        st.markdown(f'<span class="status-badge status-connected">🎯 {conf:.0%} Confidence</span>', unsafe_allow_html=True)

# Chat container
chat_container = st.container()

with chat_container:
    # Display messages
    for i, message in enumerate(st.session_state.messages):
        if message["role"] == "user":
            st.markdown(f"""
            <div style="display: flex; justify-content: flex-end; margin: 0.5rem 0;">
                <div class="message message-user">
                    {message["content"]}
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="display: flex; justify-content: flex-start; margin: 0.5rem 0;">
                <div class="message message-assistant">
                    {message["content"]}
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    # Typing indicator
    if st.session_state.typing:
        st.markdown("""
        <div style="display: flex; justify-content: flex-start; margin: 0.5rem 0;">
            <div class="message message-assistant" style="background: #F5F5F5; padding: 1rem;">
                <div class="typing-indicator">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
                <span style="font-size: 0.875rem; color: #9E9E9C;">Advisor is thinking...</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

# Recommendation card (shown after first response)
if st.session_state.recommendation and len(st.session_state.messages) >= 2:
    rec = st.session_state.recommendation
    month_name = MONTH_NAMES[rec.recommended_sell_month - 1] if rec.recommended_sell_month > 0 else "N/A"
    market_name = rec.recommended_market.value.replace("_", " ").title() if hasattr(rec.recommended_market, 'value') else str(rec.recommended_market)
    
    with st.expander("📋 **View Detailed Recommendation Card**", expanded=False):
        st.markdown(f"""
        <div class="recommendation-card">
            <div class="recommendation-row">
                <span class="rec-label">📅 Sell Month</span>
                <span class="rec-value">{month_name} (Month {rec.recommended_sell_month})</span>
            </div>
            <div class="recommendation-row">
                <span class="rec-label">🏪 Market</span>
                <span class="rec-value">{market_name}</span>
            </div>
            <div class="recommendation-row">
                <span class="rec-label">💰 Expected Price</span>
                <span class="rec-value">{format_inr(rec.expected_price_inr_per_tonne)}/tonne</span>
            </div>
            <div class="recommendation-row">
                <span class="rec-label">🚚 Logistics Cost</span>
                <span class="rec-value">{format_inr(rec.logistics_cost_inr_per_tonne)}/tonne</span>
            </div>
            <div class="recommendation-row">
                <span class="rec-label">💵 Net Price</span>
                <span class="rec-value">{format_inr(rec.net_price_inr_per_tonne)}/tonne</span>
            </div>
            <div class="recommendation-row">
                <span class="rec-label">📊 Total Revenue</span>
                <span class="rec-value">{format_inr(rec.total_revenue_inr)}</span>
            </div>
            <div class="recommendation-row">
                <span class="rec-label">💚 Net after transport</span>
                <span class="rec-value">{format_inr(rec.net_profit_inr)}</span>
            </div>
            <div class="recommendation-row">
                <span class="rec-label">🎯 Confidence</span>
                <span class="rec-value">{rec.confidence_score:.0%}</span>
            </div>
            <div class="recommendation-row">
                <span class="rec-label">🚛 Transport</span>
                <span class="rec-value">{rec.transport_mode.title()}, {rec.distance_km:,.0f} km, {rec.transit_days} days</span>
            </div>
            <div class="recommendation-row">
                <span class="rec-label">🏪 Storage</span>
                <span class="rec-value">{rec.storage_months} months</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Agent badges
        st.markdown("**Agent Contributions:**")
        agent_badges = ""
        for agent, reasoning in rec.reasoning_trace.items():
            if reasoning:
                agent_badges += f'<span class="agent-badge agent-{agent}">{agent.title()}</span> '
        st.markdown(agent_badges, unsafe_allow_html=True)
        
        # Risk tags
        if rec.risk_factors:
            st.markdown("**Risk Factors:**")
            risk_html = ""
            for risk in rec.risk_factors:
                risk_lower = risk.lower()
                risk_class = "risk-high" if any(w in risk_lower for w in ["high", "critical", "severe", "weather"]) else "risk-medium"
                risk_html += f'<span class="risk-tag {risk_class}">{risk}</span> '
            st.markdown(risk_html, unsafe_allow_html=True)
        
        # Alternatives
        if rec.alternatives:
            st.markdown("**Top Alternatives:**")
            for alt in rec.alternatives[:3]:
                alt_month = MONTH_NAMES[alt['month']-1] if alt['month'] > 0 else "N/A"
                alt_price = format_inr(alt.get('net_price_inr', alt.get('net_price', 0)))
                st.markdown(f"- **{alt_month}**: {alt_price}/tonne — {alt.get('reason', 'Alternative')}")

# Chat input
user_input = st.chat_input("Ask about when/where to sell, transport, storage, MSP, prices...")

# Handle pending quick question
if "pending_query" in st.session_state:
    user_input = st.session_state.pending_query
    del st.session_state.pending_query

# Process user input
if user_input:
    # Add user message
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Scope guard — refuse out-of-scope questions instead of silently answering
    # with whatever crop happens to be the default (bug: "tea" -> wheat advice).
    unsupported = detect_unsupported_commodity(user_input)
    no_crop_named = detect_supported_crop(user_input.lower()) is None
    if unsupported or (no_crop_named and st.session_state.recommendation is None):
        subject = f"**{unsupported}**" if unsupported else "that"
        response = (
            f"Sorry — I don't have data for {subject}, so I can't give you a "
            f"reliable answer to \"{user_input.strip()}\". I won't guess. "
            "This advisor only covers wheat, rice, maize, soybeans, barley and "
            "sorghum. Ask me about one of those and I'll help."
        )
        st.session_state.typing = False
        st.session_state.run_needed = False
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()

    # Parse natural language
    params = parse_natural_language(user_input)
    
    # Check if re-run needed
    old_params = st.session_state.simulation_params
    run_needed = (
        st.session_state.recommendation is None or
        params["crop"] != old_params.get("crop") or
        params["country"] != old_params.get("country")
    )
    
    st.session_state.simulation_params = params
    st.session_state.run_needed = run_needed  # Store in session state for next rerun
    
    # Show typing indicator
    st.session_state.typing = True
    st.rerun()

# Handle typing -> response (runs after rerun)
if st.session_state.typing:
    st.session_state.typing = False
    
    params = st.session_state.simulation_params
    user_query = st.session_state.messages[-1]["content"]
    run_needed = st.session_state.get("run_needed", True)  # Get from session state
    
    if run_needed:
        with st.spinner("🤖 Thinking..."):
            # Core simulation is deterministic; LLM (if enabled) only phrased the reply
            rec, error = run_crop_simulation(
                params["crop"], params["country"], params["year"], 
                params["area_hectares"], params["risk_tolerance"]
            )
            if error:
                response = f"❌ **Error:** {error}"
            else:
                st.session_state.recommendation = rec
                if st.session_state.use_llm and LLM_AVAILABLE:
                    response = generate_llm_response(rec, params, user_query)
                else:
                    response = generate_advice_response(rec, params)
    else:
        if st.session_state.use_llm and LLM_AVAILABLE:
            response = generate_llm_response(st.session_state.recommendation, params, user_query)
        else:
            response = generate_advice_response(st.session_state.recommendation, params)
    
    # Add assistant response
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()

# ============================================================
# FOOTER
# ============================================================
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #78909C; font-size: 0.875rem; padding: 1rem;">
    <p>🌾 <strong>Crop Sell Advisory System</strong> — Multi-Agent AI for Agricultural Decisions</p>
    <p>Built with FAOSTAT Data | Government of India MSP | Autonomous Agent Negotiation</p>
    <p><em>For advisory purposes only. Consult local agricultural officers for final decisions.</em></p>
</div>
""", unsafe_allow_html=True)