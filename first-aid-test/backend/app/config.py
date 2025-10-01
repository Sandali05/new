"""Application configuration utilities.

All sensitive settings are loaded from environment variables (optionally via a
``.env`` file). No production secrets should be committed to source control.
"""

from __future__ import annotations

import os

try:
    from dotenv import load_dotenv

    load_dotenv()  # Load variables from .env if present
except Exception:
    # ``python-dotenv`` is optional; ignore import/time errors during runtime.
    pass

# Provider API keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Astra DB / Vector store configuration
ASTRA_DB_API_ENDPOINT = os.getenv("ASTRA_DB_API_ENDPOINT", "")
ASTRA_DB_KEYSPACE = os.getenv("ASTRA_DB_KEYSPACE", "")
ASTRA_DB_DATABASE = os.getenv("ASTRA_DB_DATABASE", "")
ASTRA_DB_COLLECTION = os.getenv("ASTRA_DB_COLLECTION", "")
ASTRA_DB_APPLICATION_TOKEN = os.getenv("ASTRA_DB_APPLICATION_TOKEN", "")

# Basic flags
MODEL_PREFERENCE = os.getenv("MODEL_PREFERENCE", "groq")  # 'groq' or 'openai'
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")


def has_openai() -> bool:
    """Return True when an OpenAI API key is configured."""

    return bool(OPENAI_API_KEY)


def has_groq() -> bool:
    """Return True when a Groq API key is configured."""

    return bool(GROQ_API_KEY)


def has_astra() -> bool:
    """Return True when the Astra configuration is complete."""

    return all(
        [
            ASTRA_DB_API_ENDPOINT,
            ASTRA_DB_KEYSPACE,
            ASTRA_DB_COLLECTION,
            ASTRA_DB_APPLICATION_TOKEN,
        ]
    )
