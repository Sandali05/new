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
from ..utils import is_first_aid_related


KNOWN_EMERGENCY_TERMS = {
    "bleeding", "bruise", "burn", "scald", "sprain", "strain",
    "fracture", "break", "choke", "allergic", "anaphylaxis", "faint",
    "dizzy", "headache", "migraine", "cut", "laceration", "wound",
    "pain",
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
        sanitized_context = sec.get("sanitized", context_text)
        context_scope_hint = sec.get("in_scope")
        context_classifier_gate = emergency_classifier.classify_text(
            sanitized_context
        )

        latest_security = security_agent.protect(user_input)
        sanitized_latest = latest_security.get("sanitized", user_input)
        security_scope_hint = latest_security.get("in_scope")
        security_allowed = latest_security.get("allowed", True)

        classifier_gate = emergency_classifier.classify_text(sanitized_latest)

        # 2) Detect recovery cues so downstream components can conclude safely.
        recovery = recovery_agent.detect(history or [], user_input)

        in_scope = classifier_gate.get("is_first_aid", False)
        if not security_allowed:
            in_scope = False
        else:
            if security_scope_hint is True:
                in_scope = True
            if not in_scope and context_scope_hint:
                in_scope = True
            if not in_scope and context_classifier_gate.get("is_first_aid"):
                in_scope = True

        conversation_meta = {
            "context": context_text,
            "recovered": recovery.get("recovered"),
            "in_scope": in_scope,
            "needs_clarification": False,
            "clarification_prompt": None,
            "classifier_gate": classifier_gate,
            "context_classifier_gate": context_classifier_gate,
        }
        if session_id:
            conversation_meta["session_id"] = session_id

        if not in_scope:
            risk_stub = score_risk_confidence(
                {"category": "out_of_scope", "severity": "low"},
                {"passed": False, "skipped": True},
            )
            return {
                "rejected": True,
                "reason": "This assistant can only discuss first-aid emergencies and treatments.",
                "security": {**sec, "latest_sanitized": sanitized_latest},
                "triage": {
                    "category": "out_of_scope",
                    "severity": "low",
                    "keywords": [],
                    "confidence": classifier_gate.get("confidence", 0.0),
                },
                "instructions": {"steps": []},
                "verification": {"passed": False, "skipped": True},
                "risk_confidence": risk_stub,
                "conversation": conversation_meta,
                "recovery": recovery,
            }

        # 2) Emergency classification
        triage = emergency_classifier.classify(sanitized_latest)
        if security_allowed:
            triage_needs_context = triage.get("category") in {"out_of_scope", "unknown"}
            triage_needs_context = triage_needs_context or not triage.get("keywords")
            if triage_needs_context and context_classifier_gate.get("is_first_aid"):
                triage = emergency_classifier.classify(sanitized_context)

        in_scope = is_first_aid_related(sanitized_latest, triage)
        if not in_scope:
            context_in_scope = is_first_aid_related(sanitized_context, triage)
            if context_in_scope:
                in_scope = True

        if not security_allowed:
            in_scope = False
        elif security_scope_hint is True:
            in_scope = True
        conversation_meta["in_scope"] = in_scope

        em_numbers, maps_hint = {}, {}
        instructions = {"steps": []}
        verification_result = {"passed": True, "skipped": not in_scope}

        if in_scope:
            # 3) Get external tools via MCP-like adapter
            try:
                em_numbers = mcp_server.get_emergency_numbers()
                maps_hint = mcp_server.get_location_from_maps("nearest hospital")
            except Exception as e:
                logging.warning(f"Error getting tools from MCP server: {e}")
                # Default values are already set, so we can just log and continue

            # 4) Generate first aid instructions grounded on KB
            instructions = instruction_agent.generate(
                sanitized_latest,
                category=str(triage.get("category") or ""),
                severity=str(triage.get("severity") or ""),
            )

            # 5) Verify against guardrails
            instruction_steps = instructions.get("steps")
            if not instruction_steps:
                raise ValueError("Instruction agent did not return 'steps'")
            verification_result = verification_agent.verify(instruction_steps)

            clarification_prompt = _detect_clarification_prompt(user_input)
            needs_clarification = clarification_prompt is not None
            conversation_meta["needs_clarification"] = needs_clarification
            conversation_meta["clarification_prompt"] = clarification_prompt

        # 6) Score risk & confidence
        risk = score_risk_confidence(triage, verification_result)

        response: Dict = {
            "security": {**sec, "latest_sanitized": sanitized_latest},
            "triage": triage,
            "tools": {"emergency_numbers": em_numbers, "maps": maps_hint},
            "instructions": instructions,
            "verification": verification_result,
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
