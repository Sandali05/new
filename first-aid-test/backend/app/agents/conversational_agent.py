# agents/conversational_agent.py
# Orchestrates the flow among classifier, instruction, verification, and scoring.
from typing import Dict, List, Optional
from difflib import get_close_matches
import re
from . import (
    emergency_classifier,
    instruction_agent,
    verification_agent,
    security_agent,
    recovery_agent,
)
from ..services import mcp_server
import logging
from ..services.risk_confidence import score_risk_confidence


KNOWN_EMERGENCY_TERMS = {
    "bleeding", "bruise", "burn", "scald", "sprain", "strain",
    "fracture", "break", "choke", "allergic", "anaphylaxis", "faint",
    "dizzy", "headache", "migraine", "cut", "laceration", "wound"
}


def _gather_user_context(history: Optional[List[Dict]], user_input: str) -> str:
    """Return a condensed text string describing the recent user context."""
    if not history:
        return user_input
    user_turns = [m.get("content", "") for m in history if m.get("role") == "user"]
    user_turns.append(user_input)
    # Keep the last 3 user turns to stay focused on the current issue.
    return " \n".join(user_turns[-3:]).strip()


def _detect_clarification_prompt(text: str) -> Optional[str]:
    """Look for likely typos or ambiguous medical terms and craft a prompt."""
    tokens = re.findall(r"[a-zA-Z']+", text.lower())
    for token in tokens:
        if token in KNOWN_EMERGENCY_TERMS or len(token) < 4:
            continue
        match = get_close_matches(token, KNOWN_EMERGENCY_TERMS, n=1, cutoff=0.78)
        if match:
            guess = match[0]
            return (
                f"Got it — when you say “{token},” do you mean “{guess}” (an injury to the skin causing discoloration) "
                "or something else? If it’s that injury I can walk you through first-aid. If it’s different, could you clarify?"
            )
    return None


def handle_message(
    user_input: str,
    history: Optional[List[Dict]] = None,
    session_id: Optional[str] = None,
) -> Dict:
    try:
        # 0) Pull recent conversational context so the pipeline sees the full story.
        context_text = _gather_user_context(history, user_input)

        # 1) Security & privacy layer
        sec = security_agent.protect(context_text)
        sanitized = sec.get("sanitized", context_text)

        # 2) Emergency classification
        triage = emergency_classifier.classify(sanitized)

        # 2b) Detect recovery cues so downstream components can conclude safely.
        recovery = recovery_agent.detect(history or [], user_input)

        # 3) Get external tools via MCP-like adapter
        em_numbers, maps_hint = {}, {}
        try:
            em_numbers = mcp_server.get_emergency_numbers()
            maps_hint = mcp_server.get_location_from_maps("nearest hospital")
        except Exception as e:
            logging.warning(f"Error getting tools from MCP server: {e}")
            # Default values are already set, so we can just log and continue

        # 4) Generate first aid instructions grounded on KB
        instructions = instruction_agent.generate(sanitized)

        # 5) Verify against guardrails
        instruction_steps = instructions.get("steps")
        if not instruction_steps:
            raise ValueError("Instruction agent did not return 'steps'")
        ver = verification_agent.verify(instruction_steps)

        # 6) Score risk & confidence
        risk = score_risk_confidence(triage, ver)

        clarification_prompt = _detect_clarification_prompt(user_input)
        needs_clarification = clarification_prompt is not None

        conversation_meta = {
            "context": context_text,
            "needs_clarification": needs_clarification,
            "clarification_prompt": clarification_prompt,
        }
        if session_id:
            conversation_meta["session_id"] = session_id
        conversation_meta["recovered"] = recovery.get("recovered")

        response: Dict = {
            "security": sec,
            "triage": triage,
            "tools": {"emergency_numbers": em_numbers, "maps": maps_hint},
            "instructions": instructions,
            "verification": ver,
            "risk_confidence": risk,
            "conversation": conversation_meta,
            "recovery": recovery,
        }
        if session_id:
            response["session"] = {"id": session_id}

        return response
    except Exception as e:
        logging.error(
            f"An error occurred in the conversational agent pipeline: {e}", exc_info=True)
        return {
            "error": "An internal error occurred while processing your request.",
            "details": str(e)
        }
