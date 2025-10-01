# utils.py
from typing import List
import re

# Very small sanitizer aligned with guardrails checks
def basic_sanitize(text: str) -> str:
    # Remove suspicious characters while preserving normal punctuation
    return re.sub(r"[\x00-\x1f\x7f]", " ", text).strip()

def chunk_text(text: str, limit_tokens: int = 500, approx_chars_per_token: int = 3) -> List[str]:
    # Simple chunker to avoid provider 400 errors due to long inputs
    max_len = limit_tokens * approx_chars_per_token
    return [text[i:i+max_len] for i in range(0, len(text), max_len)]
