# utils.py
from typing import List, Dict, Optional
import re


FIRST_AID_KEYWORDS = {
    "bleed", "bleeding", "blood", "cut", "wound", "injury", "hurt",
    "pain", "ache", "aching", "burn", "scald", "bruise", "fracture",
    "sprain", "strain", "twist", "swelling", "numb", "tingling",
    "broken", "break", "dizzy", "faint", "choke", "choking", "allergic",
    "anaphylaxis", "sting", "bite", "rash", "fever", "headache",
    "migraine", "breathing", "trouble breathing", "emergency",
    "first aid", "ambulance",
}

GENERIC_TRIAGE_CATEGORIES = {
    "", "unknown", "concern", "issue", "situation", "emergency",
    "medical emergency", "non-urgent",
}

# Very small sanitizer aligned with guardrails checks
def basic_sanitize(text: str) -> str:
    # Remove suspicious characters while preserving normal punctuation
    return re.sub(r"[\x00-\x1f\x7f]", " ", text).strip()

def chunk_text(text: str, limit_tokens: int = 500, approx_chars_per_token: int = 3) -> List[str]:
    # Simple chunker to avoid provider 400 errors due to long inputs
    max_len = limit_tokens * approx_chars_per_token
    return [text[i:i+max_len] for i in range(0, len(text), max_len)]


def is_first_aid_related(user_text: str, triage: Optional[Dict]) -> bool:
    """Return True if the text appears to describe a first-aid concern."""

    lowered = (user_text or "").lower()
    if any(re.search(rf"\b{re.escape(keyword)}\b", lowered) for keyword in FIRST_AID_KEYWORDS):
        return True

    if isinstance(triage, dict):
        category = str(
            (triage.get("category") or triage.get("emergency") or "")
        ).lower()
        if category and category not in GENERIC_TRIAGE_CATEGORIES:
            return True

        triage_keywords = triage.get("keywords") or []
        for keyword in triage_keywords:
            if isinstance(keyword, str) and keyword:
                if re.search(rf"\b{re.escape(keyword.lower())}\b", lowered):
                    return True

    return False
