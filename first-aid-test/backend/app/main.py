# main.py
# FastAPI app exposing chat endpoint for the client.
from fastapi import FastAPI
import os
import requests
from .config import (
    MODEL_PREFERENCE, has_openai, has_groq, has_astra,
    ASTRA_DB_API_ENDPOINT, ASTRA_DB_KEYSPACE, ASTRA_DB_COLLECTION
)
from pydantic import BaseModel
from .agents import conversational_agent
from typing import List, Optional, Literal

Role = Literal['user', 'assistant', 'system']


class ChatMessage(BaseModel):
    role: Role
    content: str


class ChatContinueRequest(BaseModel):
    messages: List[ChatMessage]
    session_id: Optional[str] = None


def _compose_assistant_message(result: dict, user_text: str) -> str:
    # Compose a friendly assistant-style reply using available pipeline info
    text_lower = user_text.lower()
    emergency_hint = ""
    try:
        numbers = result.get("tools", {}).get("emergency_numbers", {}).get("numbers", {})
        ambulance = numbers.get("AMBULANCE") or numbers.get("ambulance") or "1990"
        if any(k in text_lower for k in ["bleeding", "spurting", "faint", "dizzy", "heavy bleeding"]):
            emergency_hint = (
                "If you’re bleeding heavily (spurting, soaking through cloth, feeling faint/dizzy), "
                f"call emergency services immediately (dial {ambulance} if available).\n\n"
            )
    except Exception:
        pass

    steps = result.get("instructions", {}).get("steps") or (
        "1) Apply gentle pressure to the area.\n"
        "2) Elevate if possible.\n"
        "3) Keep the area clean and covered.\n"
        "4) Seek professional help if symptoms worsen."
    )

    follow_up = (
        "\n\nCan you tell me where exactly and how severe it is (mild, steady, or heavy)? "
        "This helps me guide you more precisely right now."
    )

    header = "I’m here to help.\n\n"
    return header + emergency_hint + "Here’s what you can do right now:\n" + steps + follow_up


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
    result = conversational_agent.handle_message(last_user)

    # Compose assistant-style message
    assistant_text = _compose_assistant_message(result, last_user)
    new_messages = req.messages + [ChatMessage(role='assistant', content=assistant_text)]

    return {"ok": True, "messages": [m.dict() for m in new_messages], "result": result}
