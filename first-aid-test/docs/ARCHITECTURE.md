# First Aid Guide Architecture Overview

This document introduces the layout of the First Aid Guide project and highlights the
most important code paths for new contributors.

## Repository layout

```
first-aid-test/
├── backend/        # FastAPI + multi-agent orchestration layer
│   ├── app/
│   │   ├── agents/      # LLM-driven sub-agents that power the assistant
│   │   ├── services/    # Integrations (vector DB, safety rules, external tools)
│   │   ├── config.py    # Centralized configuration and feature flags
│   │   ├── main.py      # FastAPI entrypoint and HTTP routes
│   │   └── utils.py     # Shared helper functions
├── frontend/       # React client bootstrapped with Vite
│   ├── src/
│   │   ├── api.ts       # Axios client for the chat endpoints
│   │   ├── components/  # UI widgets (ChatUI)
│   │   ├── App.tsx      # Top-level component
│   │   └── main.tsx     # Application bootstrap
└── docker-compose.yml   # Local orchestration for frontend + backend
```

## Backend walkthrough

The backend is a FastAPI service that exposes three endpoints: `/api/chat`, `/api/chat/continue`,
and `/api/health`. The central workflow lives in `app/agents/conversational_agent.py` where
the message pipeline is orchestrated.

1. **Security pass** – `security_agent.protect` sanitizes the free-form text input to strip
   control characters before any downstream processing occurs.【F:backend/app/agents/conversational_agent.py†L10-L41】【F:backend/app/agents/security_agent.py†L1-L9】
2. **Emergency triage** – `emergency_classifier.classify` calls the configured LLM (Groq by
   default) to label the message with category, severity, and keywords. Failures fall back to
   a safe default payload.【F:backend/app/agents/conversational_agent.py†L16-L29】【F:backend/app/agents/emergency_classifier.py†L1-L36】
3. **Tool access** – The mocked MCP adapter provides emergency numbers and a maps hint so the
   response can reference critical contact details. This layer is designed so a real MCP server
   can be dropped in later.【F:backend/app/agents/conversational_agent.py†L18-L31】【F:backend/app/services/mcp_server.py†L1-L16】
4. **Instruction generation** – The instruction agent retrieves grounding documents from Astra DB
   (using OpenAI embeddings when available) and generates numbered first-aid steps via the chosen
   chat model. Graceful fallbacks ensure the user still receives conservative advice when external
   calls fail.【F:backend/app/agents/conversational_agent.py†L31-L37】【F:backend/app/agents/instruction_agent.py†L1-L57】
5. **Guardrails verification** – Generated steps are checked for policy violations (deny lists,
   diagnosis language) through `verification_agent`, which delegates to the YAML-driven guardrail
   module.【F:backend/app/agents/conversational_agent.py†L37-L43】【F:backend/app/services/rules_guardrails.py†L1-L40】
6. **Risk scoring** – `score_risk_confidence` combines the triage output and guardrail pass/fail
   results to estimate overall risk and our confidence in the guidance.【F:backend/app/agents/conversational_agent.py†L43-L47】【F:backend/app/services/risk_confidence.py†L1-L12】

The FastAPI endpoints simply wrap this pipeline. `/api/chat` returns the raw agent output, while
`/api/chat/continue` also synthesizes an assistant-style message via `_compose_assistant_message`,
making the backend suitable for stateful chat experiences.【F:backend/app/main.py†L1-L95】

### Configuration and services

All runtime configuration lives in `config.py`. Environment variables override the provided
assignment-friendly defaults for OpenAI, Groq, and Astra DB credentials as well as the embedding
model and provider selection flag.【F:backend/app/config.py†L1-L46】 The `services/vector_db.py`
module hosts Astra Data API helpers for upserting documents and running similarity search, while
`services/mcp_server.py` and `services/rules_guardrails.py` provide mocked integrations and safety
policies respectively.【F:backend/app/services/vector_db.py†L1-L41】【F:backend/app/services/mcp_server.py†L1-L16】【F:backend/app/services/rules_guardrails.py†L1-L40】

## Frontend walkthrough

The React frontend renders a single-page chat experience. `ChatUI` keeps local state for the
message list, call status, and error banner. When the user clicks **Send**, the component optimistically
adds the user message, invokes the `/api/chat/continue` endpoint via `continueChat`, and replaces the
state with the updated conversation returned by the backend.【F:frontend/src/components/ChatUI.tsx†L1-L61】【F:frontend/src/api.ts†L1-L33】

`App.tsx` just renders `ChatUI`, and `main.tsx` mounts the React tree. API helpers are located in
`src/api.ts`, which uses Axios against the backend routes (the Vite dev server is expected to proxy
`/api`).【F:frontend/src/App.tsx†L1-L6】【F:frontend/src/main.tsx†L1-L6】【F:frontend/src/api.ts†L1-L33】

## Running the stack

For local development, use Docker Compose to start both services. The backend serves interactive API
docs at `http://localhost:8000/docs`, and the frontend runs on `http://localhost:5173`.【F:README.md†L1-L9】

## Suggested next steps

* **Deepen safety tooling** – The guardrails module currently supports simple deny lists. Explore
  integrating richer medical guidelines or external validation APIs.
* **Real MCP integration** – Replace the stubbed `mcp_server` functions with a genuine MCP or other
  service calls for live emergency numbers and location data.
* **Frontend polish** – The chat UI is intentionally minimal. Consider adding status indicators,
  message avatars, and richer rendering of steps and risk levels.
* **Observability** – Instrument the backend with structured logging/metrics so you can track model
  latency, guardrail violations, and handoffs between agents.
* **Testing** – Add unit tests around the agent pipeline and service adapters to protect against
  regressions as you expand capabilities.
