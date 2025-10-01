# main.py
# FastAPI app exposing chat endpoint for the client.
from fastapi import FastAPI
import requests
from .config import (
    MODEL_PREFERENCE, has_openai, has_groq, has_astra,
    ASTRA_DB_API_ENDPOINT, ASTRA_DB_KEYSPACE, ASTRA_DB_COLLECTION
)
from pydantic import BaseModel
from .agents import conversational_agent, recovery_agent
from typing import List, Optional, Literal
from textwrap import dedent
import re


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


BODY_PART_KEYWORDS = {
    "head", "face", "scalp", "eye", "ear", "nose", "mouth", "jaw",
    "neck", "throat", "shoulder", "arm", "elbow", "wrist", "hand",
    "finger", "chest", "rib", "abdomen", "stomach", "back", "hip",
    "leg", "knee", "ankle", "foot", "toe", "skin"
}

TREND_KEYWORDS = {
    "worse": ["worse", "getting worse", "more", "heavier", "increasing", "spreading"],
    "better": ["better", "improving", "less", "lighter"],
    "same": ["same", "unchanged", "no change", "stable"],
}

def _detect_location_known(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(re.search(rf"\b{re.escape(part)}\b", lowered) for part in BODY_PART_KEYWORDS)


def _detect_trend(text: str) -> Optional[str]:
    if not text:
        return None
    lowered = text.lower()
    for label, keywords in TREND_KEYWORDS.items():
        for keyword in keywords:
            if keyword in lowered:
                return label
    return None


def _acknowledge_user_update(user_text: str, recovered: bool) -> str:
    if recovered:
        return "I’m really glad to hear those symptoms have cleared up."
    trend = _detect_trend(user_text)
    if trend == "worse":
        return "Thanks for telling me it’s getting worse — let’s work to slow it down."
    if trend == "better":
        return "I’m glad it seems to be improving a bit."
    if trend == "same":
        return "Thanks for the update that things feel about the same."
    return ""


def _craft_follow_up_question(
    result: dict,
    history: List[ChatMessage],
    user_text: str,
    recovered: bool,
) -> str:
    triage = result.get("triage", {}) if isinstance(result, dict) else {}
    category = (triage.get("category") or triage.get("emergency") or "concern").lower()
    severity = str(triage.get("severity") or triage.get("level") or "").lower()

    user_history_text = " \n".join(
        msg.content for msg in history if getattr(msg, "role", None) == "user"
    )
    combined_context = f"{user_history_text}\n{user_text}".strip()

    if recovered:
        return ""

    location_known = _detect_location_known(combined_context)
    trend_known = _detect_trend(combined_context)

    severe_categories = {"bleeding", "hemorrhage", "wound"}
    burn_categories = {"burn", "scald"}
    sprain_categories = {"sprain", "strain", "bruise", "contusion"}
    fracture_categories = {"fracture", "break"}

    if severity in {"high", "severe"}:
        return (
            "Do you notice any life-threatening signs such as heavy bleeding that won’t slow down, trouble breathing, or loss of consciousness?"
        )

    if category in severe_categories or any(cat in category for cat in severe_categories):
        if not location_known:
            return "Where is the bleeding coming from and how wide is the injured area?"
        if not trend_known:
            return "Is the bleeding slowing down, staying the same, or getting heavier despite pressure?"
        return "Have you been able to keep steady pressure with clean fabric or gauze on it for a full 10 minutes yet?"

    if category in burn_categories:
        if not location_known:
            return "Which part of the body was burned and how large is the area?"
        return "Are there blisters, charring, or deep white patches on the burn?"

    if category in sprain_categories:
        if not trend_known:
            return "Is the swelling improving, staying the same, or getting worse right now?"
        return "Can you still move the area, or does the pain spike when you try to bear weight or grip?"

    if category in fracture_categories:
        return "Can you avoid moving the injured limb and are you seeing any obvious deformity or numbness?"

    if not trend_known:
        return "Are the symptoms improving, staying the same, or getting worse at this moment?"

    if not location_known:
        return "Where on your body are you feeling this the most?"

    return "Is there anything new or changing that I should know about right now?"


def _compose_assistant_message(
    result: dict,
    user_text: str,
    history: List[ChatMessage],
    recovery: Optional[dict],
) -> str:
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

    recovered_flag = bool(recovery and recovery.get("recovered"))
    if recovered_flag:
        return dedent("""
            I’m really glad to hear things are feeling better now. If anything changes or the symptoms return, reach out to a healthcare professional or call your local emergency number. Take care!
        """).strip()

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

    acknowledgement = _acknowledge_user_update(user_text, recovered_flag)
    follow_up = _craft_follow_up_question(result, history, user_text, recovered_flag)

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

    response = response + verification_note

    if acknowledgement:
        response = response + "\n\n" + acknowledgement

    if follow_up:
        response = response + "\n\n" + follow_up

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
    history_payload = [m.dict() for m in req.messages]
    result = conversational_agent.handle_message(
        last_user,
        history=history_payload,
        session_id=req.session_id,
    )

    # Compose assistant-style message
    recovery_info = result.get("recovery") if isinstance(result, dict) else None
    if recovery_info is None:
        recovery_info = recovery_agent.detect(history_payload, last_user)
    assistant_text = _compose_assistant_message(result, last_user, req.messages, recovery_info)
    new_messages = req.messages + [ChatMessage(role='assistant', content=assistant_text)]

    return {
        "ok": True,
        "messages": [m.dict() for m in new_messages],
        "result": result,
        "session_id": req.session_id,
    }
