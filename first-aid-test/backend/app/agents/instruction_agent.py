# agents/instruction_agent.py
# Generates step-by-step first-aid instructions grounded by retrieved guides.
from typing import List, Dict
import logging
import requests
from ..config import MODEL_PREFERENCE, OPENAI_API_KEY, GROQ_API_KEY, EMBEDDING_MODEL, has_openai
from ..services import vector_db
from ..utils import chunk_text

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENAI_EMBED_URL = "https://api.openai.com/v1/embeddings"

def embed(text: str) -> List[float]:
    # Use OpenAI embeddings to query Astra vector search
    if not has_openai():
        logging.warning("OPENAI_API_KEY not set; returning empty embedding")
        return []
    try:
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
        r = requests.post(OPENAI_EMBED_URL, headers=headers, json={
            "model": EMBEDDING_MODEL,
            "input": text
        }, timeout=10)
        data = r.json()
        return data.get("data", [{}])[0].get("embedding", [])
    except Exception as exc:
        logging.warning("Embedding request failed: %s", exc)
        return []

def retrieve_context(query: str) -> List[Dict]:
    vec = embed(query)
    if not vec:
        return []
    return vector_db.similarity_search(vec, top_k=4)

SYSTEM = (
    "You are a First Aid instruction generator. Use provided 'context' strictly. "
    "Return clear, numbered, short steps. Include cautions. If unsure, say to contact emergency services."
)

SCENARIO_LIBRARY = [
    {
        "labels": {"bleeding", "laceration", "wound", "cut"},
        "keywords": ["bleed", "blood", "cut", "lacer", "wound", "gash", "hemorrh"],
        "steps": (
            "1) Wash your hands and gently clean the wound with clean water.\n"
            "2) Apply steady pressure with a clean cloth or bandage to slow bleeding.\n"
            "3) Elevate the injured area above heart level if possible.\n"
            "4) Seek urgent medical help if bleeding is heavy, spurting, or won't stop."
        ),
    },
    {
        "labels": {"burn", "scald"},
        "keywords": ["burn", "scald", "blister", "char"],
        "steps": (
            "1) Cool the burned area under cool running water for at least 10 minutes.\n"
            "2) Remove tight items like rings or watches before swelling starts.\n"
            "3) Cover the burn loosely with sterile, non-fluffy dressing.\n"
            "4) Avoid ointments or ice and seek medical care for large or deep burns."
        ),
    },
    {
        "labels": {"choking", "airway"},
        "keywords": ["chok", "airway", "can't breathe", "cant breathe", "heimlich"],
        "steps": (
            "1) Ask the person to cough forcefully; don't slap their back while coughing.\n"
            "2) If coughing stops, deliver 5 back blows between the shoulder blades.\n"
            "3) Follow with 5 abdominal thrusts (Heimlich) until the object clears.\n"
            "4) Call emergency services immediately if the airway stays blocked or victim becomes unresponsive."
        ),
    },
    {
        "labels": {"fainting", "dizziness"},
        "keywords": ["faint", "dizz", "lightheaded", "vertigo"],
        "steps": (
            "1) Help the person sit or lie down in a safe place right away.\n"
            "2) Loosen tight clothing and encourage slow, deep breaths.\n"
            "3) Offer sips of water if they're fully awake and not nauseated.\n"
            "4) Seek medical advice if dizziness is severe, lasts more than a few minutes, or follows a head injury."
        ),
    },
    {
        "labels": {"headache", "migraine"},
        "keywords": ["headache", "migraine", "head is aching"],
        "steps": (
            "1) Move to a quiet, dim environment and rest.\n"
            "2) Drink water to stay hydrated.\n"
            "3) Use a cold compress on the forehead or neck for short periods.\n"
            "4) Seek urgent care if headache is sudden and severe, follows injury, or includes vision or speech changes."
        ),
    },
    {
        "labels": {"sprain", "strain", "bruise", "contusion"},
        "keywords": ["sprain", "strain", "bruise", "contusion", "twist", "rolled"],
        "steps": (
            "1) Rest the injured joint and avoid putting weight on it.\n"
            "2) Apply a cold pack wrapped in cloth for 15-20 minutes every hour.\n"
            "3) Compress with an elastic bandage that's snug but not tight.\n"
            "4) Elevate above heart level and seek care if you can't bear weight or suspect a fracture."
        ),
    },
    {
        "labels": {"fracture", "broken bone"},
        "keywords": ["fracture", "broken bone", "break"],
        "steps": (
            "1) Immobilize the injured area in the position found; don't realign the limb.\n"
            "2) Apply cold packs wrapped in cloth to reduce swelling.\n"
            "3) Keep the person still and calm while you wait for help.\n"
            "4) Call emergency services or get medical help immediately."
        ),
    },
    {
        "labels": {"allergic reaction", "anaphylaxis"},
        "keywords": ["allergic", "anaphylaxis", "anaphylactic", "hives", "swelling"],
        "steps": (
            "1) Ask if the person has an epinephrine auto-injector and help them use it.\n"
            "2) Call emergency services right away.\n"
            "3) Lay the person flat with legs raised unless they're having trouble breathing.\n"
            "4) If trained, begin CPR if they stop breathing or lose pulse."
        ),
    },
]


def _fallback_steps(query: str, category: str = "") -> str:
    """Return simple, rule-based guidance when LLM calls are unavailable."""
    text = query.lower()
    category_lower = (category or "").lower()

    for scenario in SCENARIO_LIBRARY:
        if category_lower and category_lower in scenario["labels"]:
            return scenario["steps"]

    for scenario in SCENARIO_LIBRARY:
        if any(k in text for k in scenario["keywords"]):
            return scenario["steps"]

    return (
        "1) Move to a safe, comfortable position and stay calm.\n"
        "2) Check for bleeding, breathing difficulties, or other urgent symptoms.\n"
        "3) Use cool compresses, rest, or hydration as appropriate for comfort.\n"
        "4) Contact a healthcare professional or emergency services if symptoms worsen or you are unsure."
    )


def generate(query: str, *, category: str = "", severity: str = "") -> Dict:
    category_hint = (category or "").strip()
    severity_hint = (severity or "").strip()

    search_query = f"{category_hint} {query}".strip()
    context_docs = retrieve_context(search_query or query)
    context_text = "\n\n".join([d.get('document', {}).get('text','') for d in context_docs])
    # Safety against long contexts
    context_text = "\n\n".join(chunk_text(context_text, 400))
    try:
        url = GROQ_CHAT_URL if MODEL_PREFERENCE == "groq" else OPENAI_CHAT_URL
        token = GROQ_API_KEY if MODEL_PREFERENCE == 'groq' else OPENAI_API_KEY
        if not token:
            raise RuntimeError("Missing API key for selected provider")
        headers = {"Authorization": f"Bearer {token}"}
        model = "llama-3.1-70b-versatile" if MODEL_PREFERENCE == "groq" else "gpt-4o-mini"
        user_prompt = f"User description: {query}"
        if category_hint:
            user_prompt += f"\nLikely emergency category: {category_hint}."
        if severity_hint:
            user_prompt += f"\nReported severity: {severity_hint}."
        r = requests.post(url, headers=headers, json={
            "model": model,
            "messages":[
                {"role":"system","content":SYSTEM},
                {"role":"user","content":f"{user_prompt}\n\ncontext:\n{context_text}\n\nReturn numbered steps."}
            ],
            "temperature":0.2
        }, timeout=20)
        r.raise_for_status()
        content = r.json().get("choices",[{}])[0].get("message",{}).get("content","")
        if not content or content.strip().lower() == "no response":
            raise ValueError("Instruction provider returned no usable content")
    except Exception as exc:
        logging.warning("Chat generation failed: %s", exc)
        content = _fallback_steps(query, category_hint)
    return {"steps": content, "sources": [d.get('document',{}).get('_id') for d in context_docs]}
