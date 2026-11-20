"""Scope guard for the Crop Sell Advisor.

This advisor models a fixed set of food-grain crops. When a farmer asks about a
commodity outside that set, the correct behaviour is to say so — never to fall
back to the default crop and produce a confident, wrong answer.

Keeping this logic outside ``chatbot_ui.py`` makes it importable in tests without
triggering Streamlit's module-level page configuration.
"""

import re
from typing import Dict, List, Optional

# Vocabulary the UI understands. Centralised here so the parser and the guard
# cannot drift apart.
SUPPORTED_CROP_KEYWORDS: Dict[str, List[str]] = {
    "wheat": ["wheat", "gehun", "गेहूं"],
    "rice_paddy": ["rice", "paddy", "chawal", "धान", "चावल"],
    "maize": ["maize", "corn", "makka", "मक्का"],
    "soybeans": ["soybean", "soya", "soy", "सोयाबीन"],
    "barley": ["barley", "jau", "जौ"],
    "sorghum": ["sorghum", "jowar", "ज्वार"],
}

SUPPORTED_CROPS = set(SUPPORTED_CROP_KEYWORDS)

# Real agricultural commodities the advisor recognises but does NOT model.
UNSUPPORTED_COMMODITIES: Dict[str, List[str]] = {
    "tea": ["tea", "chai", "चाय"],
    "coffee": ["coffee", "कॉफी"],
    "sugarcane": ["sugarcane", "cane", "गन्ना", "ईख"],
    "cotton": ["cotton", "कपास"],
    "tobacco": ["tobacco", "तंबाकू"],
    "spices": [
        "spice", "spices", "turmeric", "haldi", "chilli", "chili", "pepper",
        "cardamom", "clove", "cinnamon", "coriander", "cumin", "मसाला",
        "हल्दी", "मिर्च", "धनिया", "जीरा",
    ],
    "pulses": [
        "pulse", "pulses", "dal", "lentil", "chickpea", "pigeon pea", "gram",
        "urad", "moong", "दाल", "चना", "मूंग", "उड़द",
    ],
    "oilseeds": [
        "mustard", "rapeseed", "groundnut", "peanut", "sunflower", "sesame",
        "safflower", "linseed", "सरसों", "मूंगफली", "सूरजमुखी", "तिल",
    ],
    "fruits": [
        "fruit", "fruits", "mango", "apple", "banana", "orange", "grapes",
        "guava", "papaya", "pineapple", "आम", "सेब", "केला", "संतरा", "अंगूर",
    ],
    "vegetables": [
        "vegetable", "vegetables", "onion", "potato", "tomato", "garlic",
        "ginger", "cabbage", "cauliflower", "प्याज", "आलू", "टमाटर", "लहसुन",
        "अदरक",
    ],
}


def _compile(keywords: List[str]) -> re.Pattern:
    return re.compile(
        r"\b(?:" + "|".join(re.escape(k) for k in keywords) + r")\b",
        re.IGNORECASE,
    )


_SUPPORTED_PATTERNS = {c: _compile(kws) for c, kws in SUPPORTED_CROP_KEYWORDS.items()}
_UNSUPPORTED_PATTERNS = {c: _compile(kws) for c, kws in UNSUPPORTED_COMMODITIES.items()}


def detect_supported_crop(query: str) -> Optional[str]:
    """Return the first supported crop named in *query*, else None."""
    if not query:
        return None
    for crop, pattern in _SUPPORTED_PATTERNS.items():
        if pattern.search(query):
            return crop
    return None


def detect_unsupported_commodity(query: str) -> Optional[str]:
    """Return the recognised-but-unsupported commodity named in *query*, else None.

    Returns the word the farmer actually used (e.g. "mango") rather than its
    category ("fruits") so the refusal message echoes their question.
    """
    if not query:
        return None
    for pattern in _UNSUPPORTED_PATTERNS.values():
        match = pattern.search(query)
        if match:
            return match.group(0).lower()
    return None
