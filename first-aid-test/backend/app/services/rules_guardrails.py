"""Utilities for enforcing YAML-defined guardrails policies."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict

import yaml

LOGGER = logging.getLogger(__name__)
GUARDRAILS_PATH = Path(__file__).resolve().parent.parent / "guardrails.yaml"


def _load_rules() -> Dict:
    if not GUARDRAILS_PATH.exists():
        LOGGER.warning("Guardrails config missing at %s; falling back to defaults", GUARDRAILS_PATH)
        return {}
    try:
        with GUARDRAILS_PATH.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except (OSError, yaml.YAMLError) as exc:
        LOGGER.warning("Unable to load guardrails config: %s", exc)
        return {}

    if not isinstance(data, dict):
        LOGGER.warning("Guardrails config must be a mapping; using empty defaults")
        return {}

    return data


RULES = _load_rules()
DISALLOWED_TOPICS = {topic.lower() for topic in RULES.get("disallowed_topics", [])}
APP_NAME = RULES.get("app_name", "first_aid_guide")
PURPOSE = RULES.get("purpose", "")
OUTPUT_RULES = RULES.get("output_rules", [])

_TOPIC_PATTERN = re.compile(r"[a-zA-Z0-9]+", re.IGNORECASE)


def policy_check(text: str) -> Dict[str, str]:
    """Return an allow/deny decision based on disallowed topics."""

    lowered = (text or "").lower()
    for topic in DISALLOWED_TOPICS:
        if not topic:
            continue
        if re.search(rf"\b{re.escape(topic)}\b", lowered):
            return {
                "allowed": False,
                "reason": f"Topic '{topic}' is outside the scope of {APP_NAME}.",
            }

    # Also check tokenized variants so multi-word phrases are caught even if punctuation differs.
    tokens = _TOPIC_PATTERN.findall(lowered)
    token_string = " ".join(tokens)
    for topic in DISALLOWED_TOPICS:
        if not topic:
            continue
        if topic in token_string:
            return {
                "allowed": False,
                "reason": f"Topic '{topic}' is outside the scope of {APP_NAME}.",
            }

    return {"allowed": True, "reason": ""}


def violates(text: str) -> bool:
    decision = policy_check(text)
    return not decision.get("allowed", True)


__all__ = [
    "policy_check",
    "violates",
    "RULES",
    "DISALLOWED_TOPICS",
    "APP_NAME",
    "PURPOSE",
    "OUTPUT_RULES",
]
