# agents/emergency_classifier.py
# Classifies user input into emergency categories using LLM prompting.
from typing import Dict
import logging
import requests
from ..config import MODEL_PREFERENCE, OPENAI_API_KEY, GROQ_API_KEY

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM = "You are an emergency triage classifier. Return JSON with fields: category, severity (low/medium/high), keywords."

def classify(text: str) -> Dict:
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
        try:
            content = resp.json()["choices"][0]["message"]["content"]
        except Exception:
            content = '{"category":"unknown","severity":"low","keywords":[]}'
    except Exception as exc:
        logging.warning("Classification failed: %s", exc)
        content = '{"category":"unknown","severity":"low","keywords":[]}'
    # Best-effort parse
    import json
    try:
        data = json.loads(content)
    except Exception:
        data = {"category":"unknown","severity":"low","keywords":[]}
    return data
