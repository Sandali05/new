# agents/security_agent.py
# Handles input sanitization and privacy redaction.
from ..utils import basic_sanitize
from typing import Dict

def protect(user_text: str) -> Dict:
    clean = basic_sanitize(user_text)
    # In a real app, mask phone/emails; here we keep it simple
    return {"sanitized": clean, "redactions": []}
