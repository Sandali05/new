"""Emergency classifier heuristics and allow-list gate."""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

from ..utils import FIRST_AID_KEYWORDS, basic_sanitize

# Minimal rule-based mapping used after the allow-list gate passes.
_CATEGORY_RULES: List[Tuple[str, List[str]]] = [
    ("bleeding", ["bleed", "blood", "cut", "lacer", "wound", "hemorrh"]),
    ("burn", ["burn", "scald", "blister", "char"]),
    ("choking", ["chok", "airway", "heimlich", "cant breathe", "can't breathe"]),
    ("allergic reaction", ["allerg", "anaphyl", "hives", "swelling"]),
    ("bruise", ["bruise", "contusion"]),
    ("sprain", ["sprain", "strain", "twist"]),
    ("fracture", ["fracture", "broken bone", "break", "crack"]),
    ("fainting", ["faint", "passed out", "dizzy", "lightheaded"]),
    ("headache", ["headache", "migraine"]),
    ("poisoning", ["poison", "overdose", "toxic"]),
]

_SEVERITY_HINTS = {
    "bleeding": "medium",
    "burn": "medium",
    "choking": "high",
    "allergic reaction": "high",
    "fracture": "high",
}

_TOKEN_PATTERN = re.compile(r"[a-zA-Z]+", re.IGNORECASE)


def _tokenize(text: str) -> List[str]:
    return _TOKEN_PATTERN.findall(text.lower())


def classify_text(text: str) -> Dict[str, object]:
    """Return allow-list based decision with a lightweight confidence score."""

    sanitized = basic_sanitize(text)
    tokens = _tokenize(sanitized)

    hits: List[str] = []
    for token in tokens:
        if token in FIRST_AID_KEYWORDS:
            hits.append(token)
            continue
        for keyword in FIRST_AID_KEYWORDS:
            if len(keyword) < 4:
                continue
            if keyword in token or token in keyword:
                hits.append(keyword)
                break

    # Include multi-word keyword matches (e.g., "first aid")
    lowered = sanitized.lower()
    for keyword in FIRST_AID_KEYWORDS:
        if " " in keyword and keyword in lowered:
            hits.append(keyword)

    unique_hits: List[str] = []
    for hit in hits:
        if hit not in unique_hits:
            unique_hits.append(hit)

    confidence = 0.0
    if unique_hits:
        confidence = min(1.0, 0.45 + 0.15 * len(unique_hits))

    label = unique_hits[0] if unique_hits else ""
    is_first_aid = confidence >= 0.6

    return {
        "is_first_aid": is_first_aid,
        "confidence": round(confidence, 3),
        "label": label,
    }


def _rule_based_classification(text: str) -> Dict[str, object]:
    lowered = text.lower()
    category = "unknown"
    matched_keywords: List[str] = []
    for label, keywords in _CATEGORY_RULES:
        if any(keyword in lowered for keyword in keywords):
            category = label
            matched_keywords = keywords[:3]
            break

    severity = "low"
    if category in _SEVERITY_HINTS:
        severity = _SEVERITY_HINTS[category]
    elif any(term in lowered for term in ("severe", "heavy", "worse", "worsening", "can't breathe", "cant breathe")):
        severity = "high"
    elif any(term in lowered for term in ("swelling", "bad", "painful", "deep", "large")):
        severity = "medium"

    return {"category": category, "severity": severity, "keywords": matched_keywords}


def classify(text: str) -> Dict[str, object]:
    """Maintain compatibility for callers needing triage metadata."""

    gate = classify_text(text)
    if not gate.get("is_first_aid"):
        return {
            "category": "out_of_scope",
            "severity": "low",
            "keywords": [],
            "confidence": gate.get("confidence", 0.0),
        }

    triage = _rule_based_classification(text)
    triage["confidence"] = gate.get("confidence", 0.0)
    triage["label"] = gate.get("label", "")
    return triage


__all__ = ["classify_text", "classify"]
