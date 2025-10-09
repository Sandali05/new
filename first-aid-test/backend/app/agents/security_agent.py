"""Input sanitisation and scope enforcement utilities."""
from __future__ import annotations

import re
from typing import Dict

from ..services import rules_guardrails
from ..utils import basic_sanitize, is_first_aid_related

_OFF_TOPIC_KEYWORDS = {
    "crypto",
    "bitcoin",
    "stock",
    "stocks",
    "invest",
    "investment",
    "homework",
    "assignment",
    "movie",
    "film",
    "recipe",
    "cook",
    "cooking",
    "code",
    "coding",
    "program",
    "programming",
    "travel",
    "vacation",
    "sports",
    "basketball",
    "football",
}


def safety_screen(user_text: str) -> Dict[str, str]:
    """Run guardrail and keyword checks to ensure the text is in scope."""

    sanitized = basic_sanitize(user_text)
    policy_decision = rules_guardrails.policy_check(sanitized)
    if not policy_decision.get("allowed", False):
        return {
            "allowed": False,
            "reason": policy_decision.get("reason")
            or "This assistant can only discuss first-aid topics.",
            "sanitized": sanitized,
        }

    lowered = sanitized.lower()
    for keyword in _OFF_TOPIC_KEYWORDS:
        if not keyword:
            continue
        if re.search(rf"\b{re.escape(keyword)}\b", lowered):
            return {
                "allowed": False,
                "reason": "This assistant can only discuss first-aid emergencies and treatments.",
                "sanitized": sanitized,
            }

    return {"allowed": True, "reason": "", "sanitized": sanitized}


def protect(user_text: str) -> Dict:
    """Return sanitized text plus a scope hint for downstream agents."""

    screen = safety_screen(user_text)
    clean = screen.get("sanitized", basic_sanitize(user_text))
    in_scope = is_first_aid_related(clean, None)
    return {
        "sanitized": clean,
        "redactions": [],
        "in_scope": in_scope if screen.get("allowed", True) else False,
        "allowed": screen.get("allowed", True),
        "reason": screen.get("reason", ""),
    }


__all__ = ["safety_screen", "protect"]
