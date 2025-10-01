# agents/conversational_agent.py
# Orchestrates the flow among classifier, instruction, verification, and scoring.
from typing import Dict
from . import emergency_classifier, instruction_agent, verification_agent, security_agent
from ..services import mcp_server
import logging
from ..services.risk_confidence import score_risk_confidence


def handle_message(user_input: str) -> Dict:
    try:
        # 1) Security & privacy layer
        sec = security_agent.protect(user_input)
        sanitized = sec.get("sanitized", user_input)

        # 2) Emergency classification
        triage = emergency_classifier.classify(sanitized)

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

        return {
            "security": sec,
            "triage": triage,
            "tools": {"emergency_numbers": em_numbers, "maps": maps_hint},
            "instructions": instructions,
            "verification": ver,
            "risk_confidence": risk,
        }
    except Exception as e:
        logging.error(
            f"An error occurred in the conversational agent pipeline: {e}", exc_info=True)
        return {
            "error": "An internal error occurred while processing your request.",
            "details": str(e)
        }
