# agents/emergency_classifier.py
# Classifies user input into emergency categories using LLM prompting.
from typing import Dict, List
import logging
import requests
from ..config import MODEL_PREFERENCE, OPENAI_API_KEY, GROQ_API_KEY

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM = "You are an emergency triage classifier. Return JSON with fields: category, severity (low/medium/high), keywords."


def _rule_based_classification(text: str) -> Dict:
    """Provide an offline fallback categorisation when LLM access is unavailable."""

    lowered = text.lower()

    def _matches(keywords: List[str]) -> bool:
        return any(kw in lowered for kw in keywords)

    rules = [
        ("bleeding", ["bleed", "blood", "cut", "lacer", "wound", "gash", "hemorrh"]),
        ("burn", ["burn", "scald", "blister", "char" ]),
        ("choking", ["chok", "can't breathe", "cant breathe", "airway", "heimlich"]),
        ("allergic reaction", ["allergic", "anaphyl", "hives", "swelling" ]),
        ("bruise", ["bruise", "contusion" ]),
        ("sprain", ["sprain", "strain", "twist" ]),
        ("fracture", ["fracture", "broken bone", "break" ]),
        ("fainting", ["faint", "passed out", "dizzy", "lightheaded" ]),
        ("headache", ["headache", "migraine" ]),
    ]

    category = "unknown"
    matched_keywords: List[str] = []
    for label, keywords in rules:
        if _matches(keywords):
            category = label
            matched_keywords = list(keywords)
            break

    severity = "low"
    if _matches(["severe", "heavy", "spurting", "gushing", "can't breathe", "cant breathe", "unconscious", "not breathing", "numb", "no feeling"]):
        severity = "high"
    elif _matches(["worse", "swelling", "getting worse", "bad", "painful", "deep", "large", "can't move", "cant move"]):
        severity = "medium"

    if category in {"choking", "allergic reaction", "fracture"}:
        severity = "high"
    elif category in {"bleeding", "burn", "sprain"} and severity == "low":
        severity = "medium"

    keywords = matched_keywords[:3] if matched_keywords else []

    return {"category": category, "severity": severity, "keywords": keywords}


def classify(text: str) -> Dict:
    content = None
    try:
        url = GROQ_CHAT_URL if MODEL_PREFERENCE == "groq" else OPENAI_CHAT_URL
        token = GROQ_API_KEY if MODEL_PREFERENCE == 'groq' else OPENAI_API_KEY
        if not token:
            raise RuntimeError("Missing API key for selected provider")
        headers = {"Authorization": f"Bearer {token}"}
        model = "llama-3.1-70b-versatile" if MODEL_PREFERENCE == "groq" else "gpt-4o-mini"
        resp = requests.post(url, headers=headers, json={
            "model": model,
            "messages": [
                {"role":"system","content": SYSTEM},
                {"role":"user","content": f"Text: {text}\nReturn JSON only."}
            ],
            "temperature": 0.1
        }, timeout=15)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        logging.warning("Classification failed: %s", exc)

    import json
    data: Dict = {"category": "unknown", "severity": "low", "keywords": []}
    if content:
        try:
            data = json.loads(content)
        except Exception as parse_exc:
            logging.debug("Failed to parse classifier response %s: %s", content, parse_exc)

    fallback = _rule_based_classification(text)

    if not data.get("category") or data.get("category", "").lower() == "unknown":
        data.update(fallback)
    elif fallback.get("keywords") and not data.get("keywords"):
        data["keywords"] = fallback["keywords"]

    severity = str(data.get("severity", "")).lower()
    if severity not in {"low", "medium", "high"}:
        data["severity"] = fallback["severity"]

    return data
