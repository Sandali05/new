# agents/verification_agent.py
# Cross-checks generated instructions against multiple sources / heuristics.
from typing import Dict
from ..services import rules_guardrails as guardrails

def verify(generated_text: str) -> Dict:
    # Very simple policy checks with guardrails; extend with more signals (NLM, UMLS, etc.)
    violations = guardrails.violates(generated_text)
    return {
        "passed": not violations,
        "policy_flags": ["guardrails_violation"] if violations else []
    }
