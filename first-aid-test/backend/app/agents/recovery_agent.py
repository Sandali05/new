"""Agent utilities for detecting recovery cues in user conversations."""
from typing import Iterable, List, Optional, Union, Dict
import re

# Patterns indicating the user reports resolution of their symptoms.
RECOVERY_PATTERNS: List[str] = [
    r"\ball good now\b",
    r"\ball better now\b",
    r"\bfeeling (?:fine|okay|ok) now\b",
    r"\bno (?:longer|more) (?:hurting|hurt|pain|bleeding)\b",
    r"\bnot (?:painful|hurting) anymore\b",
    r"\bpain (?:is )?gone\b",
    r"\bbleeding (?:has )?stopped\b",
    r"\bit'?s healed now\b",
]

MessageLike = Union[Dict[str, str], object]


def _extract_user_content(message: MessageLike) -> Optional[str]:
    """Return the user-authored text from a chat message like object."""
    if isinstance(message, dict):
        if message.get("role") != "user":
            return None
        return message.get("content") or ""
    role = getattr(message, "role", None)
    if role != "user":
        return None
    return getattr(message, "content", "") or ""


def _gather_recent_text(history: Optional[Iterable[MessageLike]], latest_input: str) -> str:
    """Combine recent user turns with the latest user input."""
    texts: List[str] = []
    if history:
        for item in history:
            content = _extract_user_content(item)
            if content:
                texts.append(content)
    if latest_input:
        texts.append(latest_input)
    return "\n".join(texts).strip()


def detect(history: Optional[Iterable[MessageLike]], latest_input: str) -> Dict[str, object]:
    """Detect whether the user has indicated recovery.

    Returns a dictionary so downstream callers can attach this agent's
    observations to their own payloads.
    """
    combined = _gather_recent_text(history, latest_input)
    lowered = combined.lower()
    matches: List[str] = [pattern for pattern in RECOVERY_PATTERNS if re.search(pattern, lowered)]
    return {
        "recovered": bool(matches),
        "matches": matches,
        "window": combined,
    }
