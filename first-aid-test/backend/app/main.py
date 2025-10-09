# main.py
# FastAPI app exposing chat endpoint for the client.
from fastapi import Depends, FastAPI, HTTPException, status
import requests
from .config import (
    MODEL_PREFERENCE, has_openai, has_groq, has_astra,
    ASTRA_DB_API_ENDPOINT, ASTRA_DB_KEYSPACE, ASTRA_DB_COLLECTION
)
from pydantic import BaseModel
from .agents import conversational_agent, recovery_agent, security_agent, emergency_classifier
from .utils import is_first_aid_related
from typing import Annotated, List, Optional, Literal
from textwrap import dedent
import re


Role = Literal['user', 'assistant', 'system']


class ChatMessage(BaseModel):
    role: Role
    content: str


class ChatContinueRequest(BaseModel):
    messages: List[ChatMessage]
    session_id: Optional[str] = None


FIRST_AID_ONLY_MESSAGE = "This assistant can only respond to first-aid emergencies and treatments."


def _latest_user_message(messages: List[ChatMessage]) -> Optional[ChatMessage]:
    for message in reversed(messages):
        if message.role == "user":
            return message
    return None


def validate_first_aid_intent(payload: ChatContinueRequest) -> ChatContinueRequest:
    latest_user = _latest_user_message(payload.messages)
    if latest_user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=FIRST_AID_ONLY_MESSAGE,
        )

    screen = security_agent.safety_screen(latest_user.content)
    if not screen.get("allowed", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=screen.get("reason") or FIRST_AID_ONLY_MESSAGE,
        )

    classification = emergency_classifier.classify_text(screen.get("sanitized", latest_user.content))
    if not classification.get("is_first_aid"):
        user_turns = [m.content for m in payload.messages if m.role == "user"]
        if len(user_turns) > 1:
            context_text = "\n".join(user_turns[-3:]).strip()
            if context_text and context_text != latest_user.content.strip():
                context_screen = security_agent.safety_screen(context_text)
                if context_screen.get("allowed", True):
                    context_classification = emergency_classifier.classify_text(
                        context_screen.get("sanitized", context_text)
                    )
                    if context_classification.get("is_first_aid"):
                        return payload

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=FIRST_AID_ONLY_MESSAGE,
        )

    return payload


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

TREND_PATTERNS = {
    "worse": [
        r"\bgetting worse\b",
        r"\bworsening\b",
        r"\bworse\b",
        r"\bheavier\b",
        r"\bincreasing\b",
        r"\bspreading\b",
        r"\bmore (?:pain|bleeding|swelling|numbness)\b",
    ],
    "better": [
        r"\bgetting better\b",
        r"\bbetter\b",
        r"\bimproving\b",
        r"\bimproved\b",
        r"\bless (?:pain|bleeding|swelling)\b",
        r"\blighter\b",
        r"\bsubsiding\b",
    ],
    "same": [
        r"\babout the same\b",
        r"\bstaying the same\b",
        r"\bno change\b",
        r"\bunchanged\b",
        r"\bstable\b",
    ],
}


def _tailor_steps_for_context(
    original_steps: str,
    triage: dict,
    trend: Optional[str],
    severity_raw: str,
    ambulance_number: str,
    repeated_steps: bool,
) -> str:
    """Provide situation-aware guidance when the base instructions repeat."""

    if not repeated_steps:
        return original_steps

    category = (triage.get("category") or triage.get("emergency") or "").lower()
    severity_normalized = str(severity_raw or "").lower()

    def _format(lines: List[str]) -> str:
        return "\n\n".join(line.strip() for line in lines if line.strip())

    emergency_prompt = (
        f"Call {ambulance_number} or head to the nearest emergency department right away."
        if ambulance_number
        else "Contact emergency services immediately."
    )

    if trend == "worse" or severity_normalized in {"high", "severe"}:
        if any(key in category for key in ("fracture", "break")):
            return _format([
                "1. Keep the injured limb immobilized exactly as it is — don’t try to straighten, test, or massage it.",
                f"2. Because the symptoms are getting worse, {emergency_prompt}",
                "3. Continue using cold packs wrapped in cloth for up to 20 minutes at a time and keep the limb elevated above heart level.",
                "4. Watch closely for numbness, tingling, pale or bluish skin, or loss of feeling and report those changes to professionals immediately.",
            ])
        if any(key in category for key in ("bleed", "wound", "lacer", "hemorrhage")):
            return _format([
                "1. Maintain firm, direct pressure on the wound without lifting the cloth or gauze to check it.",
                f"2. Have someone else {emergency_prompt.lower()} while you keep pressure on the area.",
                "3. Keep the injured area elevated above heart level if possible and add clean cloths on top if blood soaks through.",
                "4. If the person gets lightheaded, clammy, or very pale, lie them flat and raise their legs until help arrives.",
            ])
        if any(key in category for key in ("burn", "scald")):
            return _format([
                "1. Continue cooling the burn under cool (not icy) running water for 10–20 minutes total if you haven’t already.",
                "2. Cover it loosely with sterile, non-fluffy dressing or clean cloth after cooling — don’t apply ointments or pop blisters.",
                f"3. Because pain or damage is increasing, {emergency_prompt}",
                "4. Keep jewelry or tight clothing off the area and monitor for difficulty breathing or signs of shock.",
            ])
        if any(key in category for key in ("allergic", "anaphyl")):
            return _format([
                "1. Use an epinephrine auto-injector immediately if one is available and you’re trained.",
                f"2. Because symptoms are escalating, {emergency_prompt}",
                "3. Lay the person flat with legs raised unless they’re struggling to breathe, and loosen tight clothing.",
                "4. If breathing or pulse stops, begin CPR if you’re trained while waiting for emergency responders.",
            ])
        return _format([
            "1. Keep following the earlier first-aid steps exactly as discussed.",
            f"2. Since things are getting worse, {emergency_prompt}",
            "3. Limit movement, keep monitoring vital signs, and prepare for emergency responders with location details.",
            "4. If anyone nearby can assist, have them gather medications, allergies, and medical history for paramedics.",
        ])

    if trend == "same":
        return _format([
            "1. Continue carrying out the first-aid steps we already reviewed.",
            "2. Re-check the area every 10–15 minutes for changes in color, swelling, numbness, or pain spikes.",
            "3. Keep resting the area and avoid anything that might aggravate the injury or condition.",
            f"4. If the situation starts to worsen or new symptoms appear, {emergency_prompt}",
        ])

    if trend == "better":
        return _format([
            "1. Great news — keep gently following the earlier steps while symptoms settle down.",
            "2. Gradually space out ice, compression, or medication only if comfort keeps improving.",
            "3. Protect the area from bumps or strain until it’s fully healed.",
            f"4. If pain returns, discoloration develops, or new symptoms show up, {emergency_prompt}",
        ])

    return _format([
        "1. Continue the prior first-aid guidance as closely as possible.",
        "2. Observe the situation for any new warning signs like spreading pain, fever, numbness, or difficulty breathing.",
        "3. Rest, hydrate, and avoid stress on the affected area while you monitor.",
        f"4. Reach a healthcare professional or {ambulance_number or 'emergency services'} promptly if anything changes or you’re unsure.",
    ])

def _detect_location_known(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(re.search(rf"\b{re.escape(part)}\b", lowered) for part in BODY_PART_KEYWORDS)


def _detect_trend(text: str) -> Optional[str]:
    if not text:
        return None
    lowered = text.lower()
    for label, patterns in TREND_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, lowered):
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
    recovered_flag = bool(recovery and recovery.get("recovered"))

    if result.get("error"):
        return (
            "I’m sorry — something went wrong while processing that. "
            "Please try again, and if it keeps failing seek emergency care if you’re in danger."
        )

    if recovered_flag:
        return dedent("""
            I’m really glad to hear things are feeling better now. If anything changes or the symptoms return, reach out to a healthcare professional or call your local emergency number. Take care!
        """).strip()

    triage = result.get("triage", {})
    sanitized_latest = result.get("security", {}).get("latest_sanitized", user_text)

    conversation_scope = conversation_meta.get("in_scope")
    if conversation_scope is None:
        conversation_scope = is_first_aid_related(sanitized_latest, triage)

    if not conversation_scope:
        return dedent("""
            I’m built to help with first-aid concerns. If you have a medical question or emergency, please share the symptoms or injuries you’re experiencing.
        """).strip()

    if conversation_meta.get("needs_clarification"):
        prompt = conversation_meta.get("clarification_prompt")
        if prompt:
            return prompt
        return (
            "I want to be sure I understand the situation. Could you share what happened, where it hurts, and how severe it is?"
        )

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

    user_trend = _detect_trend(user_text)
    last_assistant_msg = next((m for m in reversed(history) if getattr(m, "role", None) == "assistant"), None)
    repeated_steps = bool(
        last_assistant_msg
        and steps_text
        and steps_text in (last_assistant_msg.content if getattr(last_assistant_msg, "content", None) else "")
    )
    steps_text = _tailor_steps_for_context(
        steps_text,
        triage,
        user_trend,
        severity,
        ambulance_number,
        repeated_steps,
    )

    acknowledgement = _acknowledge_user_update(user_text, recovered_flag)
    follow_up = _craft_follow_up_question(result, history, user_text, recovered_flag)

    critical_hint = ""
    if str(severity).lower() in {"high", "severe"}:
        critical_hint = (
            f"If anything feels life-threatening, call emergency services immediately (dial {ambulance_number}).\n\n"
        )

    caution_note = ""
    severity_level = str(severity).lower()
    if not verification_note and (
        severity_level in {"high", "severe", "serious"}
        or (user_trend == "worse" and severity_level not in {"low", "mild"})
    ):
        caution_note = (
            "\n\n⚠️ I noticed something that may conflict with our safety checks. "
            "Please double-check with emergency services or a medical professional."
        )

    response = dedent(f"""
        I’m here to help.

        🩺 What I’m seeing
        • Concern type: {category}
        • Severity: {severity_text}

        ✅ Trusted first-aid steps
        {steps_text}
    """).strip()

    response = response + verification_note + caution_note

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


ValidatedChatRequest = Annotated[ChatContinueRequest, Depends(validate_first_aid_intent)]


@app.post("/api/chat/continue")
def chat_continue(req: ValidatedChatRequest):
    # Find the latest user message (dependency already ensured a user turn exists)
    last_user = next(m.content for m in reversed(req.messages) if m.role == "user")

    # Run existing pipeline on the last user message
    history_payload = [m.dict() for m in req.messages]
    result = conversational_agent.handle_message(
        last_user,
        history=history_payload,
        session_id=req.session_id,
    )

    if isinstance(result, dict) and result.get("rejected"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("reason", FIRST_AID_ONLY_MESSAGE),
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
