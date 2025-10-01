# services/risk_confidence.py
# Simple heuristic for risk and confidence
from typing import Dict

SEVERITY_MAP = {"low": 0.2, "medium": 0.6, "high": 0.9}

def score_risk_confidence(triage: Dict, verification: Dict) -> Dict:
    sev = SEVERITY_MAP.get(str(triage.get("severity","low")).lower(), 0.2)
    verify_bonus = 0.2 if verification.get("passed") else -0.3
    risk = min(1.0, max(0.0, sev + (0.1 if "bleeding" in str(triage).lower() else 0.0)))
    confidence = min(1.0, max(0.0, 0.5 + verify_bonus))
    return {"risk": risk, "confidence": confidence}
