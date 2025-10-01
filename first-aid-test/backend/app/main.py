# main.py
# FastAPI app exposing chat endpoint for the client.
from fastapi import FastAPI
import requests
from .config import (
    MODEL_PREFERENCE, has_openai, has_groq, has_astra,
    ASTRA_DB_API_ENDPOINT, ASTRA_DB_KEYSPACE, ASTRA_DB_COLLECTION
)
from pydantic import BaseModel
from .agents import conversational_agent
from typing import List, Optional, Literal
from textwrap import dedent


Role = Literal['user', 'assistant', 'system']


class ChatMessage(BaseModel):
    role: Role
    content: str


class ChatContinueRequest(BaseModel):
    messages: List[ChatMessage]
    session_id: Optional[str] = None


def _normalize_steps(steps) -> str:
    if isinstance(steps, list):
        return "\n".join(f"{idx+1}. {s}" for idx, s in enumerate(steps))
    return str(steps or "")


def _compose_assistant_message(result: dict, user_text: str, history: List[ChatMessage]) -> str:
    conversation_meta = result.get("conversation", {}) if isinstance(result, dict) else {}
    if result.get("error"):
        return (
            "I’m sorry — something went wrong while processing that. "
            "Please try again, and if it keeps failing seek emergency care if you’re in danger."
        )

    if conversation_meta.get("needs_clarification"):
        prompt = conversation_meta.get("clarification_prompt")
        if prompt:
            return prompt
        return (
            "I want to be sure I understand the situation. Could you share what happened, where it hurts, and how severe it is?"
        )

    triage = result.get("triage", {})
    severity = triage.get("severity") or triage.get("level") or "unknown"
    category = triage.get("category") or triage.get("emergency") or "concern"

    steps_raw = result.get("instructions", {}).get("steps")
    steps_text = _normalize_steps(steps_raw).strip()
    if not steps_text:
        steps_text = dedent("""
            1. Move to a safe position and stay calm.
            2. Check for bleeding, breathing trouble, or other severe signs.
            3. Use rest, ice, or gentle pressure as appropriate for comfort.
            4. Contact emergency services if symptoms worsen or you’re unsure.
        """).strip()

    numbers = result.get("tools", {}).get("emergency_numbers", {}).get("numbers", {})
    ambulance_number = numbers.get("AMBULANCE") or numbers.get("ambulance") or "local emergency number"

    verification = result.get("verification", {})
    verification_note = ""
    if not verification.get("passed", True):
        verification_note = (
            "\n\n⚠️ I noticed something that may conflict with our safety checks. "
            "Please double-check with emergency services or a medical professional."
        )

    severity_language = {
        "high": "serious",
        "medium": "moderate",
        "low": "mild",
    }
    severity_text = severity_language.get(str(severity).lower(), "uncertain")

    follow_up = (
        "\n\nCould you tell me exactly where it is and whether the symptoms are getting better, worse, or staying the same?"
    )

    critical_hint = ""
    if str(severity).lower() in {"high", "severe"}:
        critical_hint = (
            f"If anything feels life-threatening, call emergency services immediately (dial {ambulance_number}).\n\n"
        )

    response = dedent(f"""
        I’m here to help.

        🩺 What I’m seeing
        • Concern type: {category}
        • Severity: {severity_text}

        ✅ Trusted first-aid steps
        {steps_text}
    """).strip()

    response = response + verification_note + follow_up

    if critical_hint:
        response = "If you feel faint, see heavy bleeding, or anything seems life-threatening, call emergency services immediately.\n\n" + response

    return response


app = FastAPI(title="FirstAidGuide - Multi-Agent API")

class ChatRequest(BaseModel):
    message: str

@app.post("/api/chat")
def chat(req: ChatRequest):
    # Orchestrate the multi-agent flow
    result = conversational_agent.handle_message(req.message)
    return {"ok": True, "result": result}

@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/health/details")
def health_details():
    details = {"ok": True}
    # Config presence
    details["config"] = {
        "model_preference": MODEL_PREFERENCE,
        "has_openai_key": has_openai(),
        "has_groq_key": has_groq(),
        "has_astra_config": has_astra(),
    }
    # Shallow external reachability checks (no secrets)
    checks = {}
    try:
        r = requests.get("https://api.openai.com/v1/models", timeout=3)
        checks["openai_models_head"] = r.status_code
    except Exception as exc:
        checks["openai_models_head"] = str(exc)
    try:
        r = requests.get("https://api.groq.com/openai/v1/models", timeout=3)
        checks["groq_models_head"] = r.status_code
    except Exception as exc:
        checks["groq_models_head"] = str(exc)
    if has_astra():
        try:
            r = requests.get(ASTRA_DB_API_ENDPOINT, timeout=3)
            checks["astra_endpoint"] = r.status_code
        except Exception as exc:
            checks["astra_endpoint"] = str(exc)
    details["connectivity"] = checks
    details["astra"] = {
        "endpoint_set": bool(ASTRA_DB_API_ENDPOINT),
        "keyspace_set": bool(ASTRA_DB_KEYSPACE),
        "collection_set": bool(ASTRA_DB_COLLECTION),
    }
    return details


@app.post("/api/chat/continue")
def chat_continue(req: ChatContinueRequest):
    # Find the latest user message
    user_msgs = [m for m in req.messages if m.role == 'user']
    if not user_msgs:
        return {"ok": False, "error": "No user message provided"}
    last_user = user_msgs[-1].content

    # Run existing pipeline on the last user message
    history = [m.dict() for m in req.messages]
    result = conversational_agent.handle_message(last_user, history)

    # Compose assistant-style message
    assistant_text = _compose_assistant_message(result, last_user, req.messages)
    new_messages = req.messages + [ChatMessage(role='assistant', content=assistant_text)]

    return {"ok": True, "messages": [m.dict() for m in new_messages], "result": result}
