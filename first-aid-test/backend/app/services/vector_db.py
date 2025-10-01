# services/vector_db.py
# Minimal Astra DB Vector integration via REST Data API
import requests, json
import logging
from typing import List, Dict, Any
from . import rules_guardrails as guardrails
from ..config import (
    ASTRA_DB_API_ENDPOINT, ASTRA_DB_KEYSPACE, ASTRA_DB_DATABASE,
    ASTRA_DB_COLLECTION, ASTRA_DB_APPLICATION_TOKEN, has_astra
)

BASE = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/{ASTRA_DB_KEYSPACE}" if ASTRA_DB_API_ENDPOINT and ASTRA_DB_KEYSPACE else ""
HEADERS = {
    "Content-Type": "application/json",
    "x-cassandra-token": ASTRA_DB_APPLICATION_TOKEN
} if ASTRA_DB_APPLICATION_TOKEN else {"Content-Type": "application/json"}

def upsert_documents(docs: List[Dict[str, Any]]):
    # docs: [{_id?, text, embedding?, meta?}]
    if not has_astra():
        logging.warning("Astra configuration missing; skipping upsert")
        return []
    url = f"{BASE}/collections/{ASTRA_DB_COLLECTION}"
    resps = []
    for d in docs:
        try:
            payload = {"document": d}
            r = requests.post(url, headers=HEADERS, data=json.dumps(payload), timeout=10)
            resps.append((r.status_code, r.text))
        except Exception as exc:
            logging.warning("Astra upsert failed: %s", exc)
            resps.append((0, str(exc)))
    return resps

def similarity_search(embedding: List[float], top_k: int = 4) -> List[Dict[str, Any]]:
    # Astra JSON API vector search shape
    if not has_astra() or not embedding:
        return []
    try:
        url = f"{BASE}/collections/{ASTRA_DB_COLLECTION}/vector-search"
        payload = {"topK": top_k, "vector": embedding, "includeSimilarity": True}
        r = requests.post(url, headers=HEADERS, data=json.dumps(payload), timeout=15)
        if r.status_code != 200:
            return []
        data = r.json()
        return data.get("documents", [])
    except Exception as exc:
        logging.warning("Astra similarity search failed: %s", exc)
        return []
