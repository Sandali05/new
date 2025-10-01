# services/rules_guardrails.py
# This module loads/validates guardrails from YAML; here we keep minimal helpers.
import logging
import re
from pathlib import Path

import yaml

LOGGER = logging.getLogger(__name__)
GUARDRAILS_PATH = Path(__file__).resolve().parent.parent / "guardrails.yaml"


def _load_rules() -> dict:
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

# Simple evaluators for demo
DENYLIST = set(RULES.get("deny_terms", []))
BLOCK_MEDICAL_DIAGNOSIS = RULES.get("block_unqualified_medical_diagnosis", True)


def violates(text: str) -> bool:
    t = text.lower()
    if any(term.lower() in t for term in DENYLIST):
        return True
    # prevent prescriptive diagnosis strings
    if BLOCK_MEDICAL_DIAGNOSIS and re.search("diagnose|prescribe|dose\\b", t, re.I):
        return True
    return False
