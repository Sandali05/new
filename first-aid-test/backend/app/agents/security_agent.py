# agents/security_agent.py
# Handles input sanitization, privacy redaction, and scope hints.
from typing import Dict

from ..utils import basic_sanitize, is_first_aid_related


def protect(user_text: str) -> Dict:
    clean = basic_sanitize(user_text)

    # Determine whether the sanitized text itself appears within the first-aid scope.
    in_scope = is_first_aid_related(clean, None)

    # In a real app, mask phone/emails; here we keep it simple but expose the scope flag.
    return {
        "sanitized": clean,
        "redactions": [],
        "in_scope": in_scope,
    }
