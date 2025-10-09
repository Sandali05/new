# Backend and Frontend File Reference

This reference explains the purpose and integration role of every file inside the repository's backend and frontend directories.

## Backend

### backend/Dockerfile
Defines the container image for the FastAPI service: installs Python dependencies from `requirements.txt`, copies the application package, exposes port 8000, and starts Uvicorn with `app.main:app`. 【F:backend/Dockerfile†L1-L9】

### backend/requirements.txt
Pins the Python packages FastAPI needs at runtime (FastAPI, Uvicorn, Pydantic, Requests, PyYAML, python-dotenv) so the backend environment is reproducible. 【F:backend/requirements.txt†L1-L6】

### backend/app/config.py
Loads configuration from environment variables (optionally via `.env`) for provider API keys, Astra DB access, and feature toggles, and exposes helper functions indicating whether integrations such as OpenAI, Groq, or Astra are available. 【F:backend/app/config.py†L1-L51】

### backend/app/main.py
Implements the FastAPI application: validates chat requests, runs the multi-agent pipeline, tailors assistant responses with triage metadata, exposes health endpoints, and orchestrates `/api/chat` and `/api/chat/continue`. 【F:backend/app/main.py†L1-L203】【F:backend/app/main.py†L203-L402】【F:backend/app/main.py†L402-L479】

### backend/app/astra_test.py
Standalone script for manually exercising the Astra Data API by upserting and fetching a test document using the configured credentials. 【F:backend/app/astra_test.py†L1-L23】

### backend/app/guardrails.yaml
YAML policy configuration listing disallowed topics and response rules that guardrails enforcement modules use to keep conversations on first-aid guidance. 【F:backend/app/guardrails.yaml†L1-L12】

### backend/app/utils.py
Provides shared keyword lists, sanitization helpers, text chunking, and heuristics for determining whether a user message relates to first aid—utilities consumed by multiple agents. 【F:backend/app/utils.py†L1-L79】

### backend/app/agents/security_agent.py
Sanitizes incoming text, checks it against disallowed topics, and returns scope hints for downstream agents, leveraging the guardrails service. 【F:backend/app/agents/security_agent.py†L1-L57】

### backend/app/agents/emergency_classifier.py
Contains allow-list gating and rule-based triage logic that labels first-aid categories, estimates severity, and supplies metadata used throughout the conversation pipeline. 【F:backend/app/agents/emergency_classifier.py†L1-L94】

### backend/app/agents/recovery_agent.py
Detects when users report recovery, scanning both the latest and previous messages so the assistant can close loops appropriately. 【F:backend/app/agents/recovery_agent.py†L1-L66】

### backend/app/agents/instruction_agent.py
Combines retrieval-augmented generation and deterministic fallbacks to produce numbered first-aid steps, using embeddings, Astra vector search, and Groq/OpenAI chat models when configured. 【F:backend/app/agents/instruction_agent.py†L1-L139】【F:backend/app/agents/instruction_agent.py†L139-L199】

### backend/app/agents/verification_agent.py
Checks generated instructions against guardrail rules and flags potential violations to support safe responses. 【F:backend/app/agents/verification_agent.py†L1-L11】

### backend/app/agents/conversational_agent.py
Orchestrates the full multi-agent workflow: aggregates context, invokes security, classification, instruction, verification, recovery, tool adapters, and risk scoring to produce a structured result payload. 【F:backend/app/agents/conversational_agent.py†L1-L134】

### backend/app/services/rules_guardrails.py
Loads the YAML policy file, exposes allow/deny checks for topics, and wraps guardrail utilities reused by multiple agents. 【F:backend/app/services/rules_guardrails.py†L1-L70】

### backend/app/services/risk_confidence.py
Implements heuristic risk and confidence scoring derived from triage severity and verification outcomes. 【F:backend/app/services/risk_confidence.py†L1-L10】

### backend/app/services/mcp_server.py
Simulates MCP tool calls, returning mock emergency numbers, map lookups, and placeholder API responses that enrich the agent output. 【F:backend/app/services/mcp_server.py†L1-L15】

### backend/app/services/vector_db.py
Wraps the Astra Data API for document upserts and similarity search while gracefully handling missing credentials, powering retrieval for instruction generation. 【F:backend/app/services/vector_db.py†L1-L43】

## Frontend

### frontend/dockerfile
Defines the Node-based development container for the Vite/React UI, installing dependencies and running `npm run dev` on port 5173. 【F:frontend/dockerfile†L1-L13】

### frontend/package.json
Declares the React application's metadata, scripts, runtime dependencies (React, Axios), and dev tooling (TypeScript, Vite, React plugin). 【F:frontend/package.json†L1-L21】

### frontend/package-lock.json
Locks the exact npm dependency graph for reproducible installs, capturing resolved versions and integrity hashes for every package the frontend uses. 【F:frontend/package-lock.json†L1-L34】

### frontend/node_modules/.package-lock.json
Local copy of the generated lockfile stored within `node_modules`, mirroring dependency resolution details for tooling that reads in-place metadata. 【F:frontend/node_modules/.package-lock.json†L1-L18】

### frontend/index.html
Minimal HTML shell that Vite serves, containing only the root mounting div and module script that bootstraps the React app. 【F:frontend/index.html†L1-L11】

### frontend/vite.config.js
Configures Vite with the React plugin and a development proxy that forwards `/api` calls to the backend server selected via `VITE_PROXY_TARGET`. 【F:frontend/vite.config.js†L1-L16】

### frontend/src/main.tsx
Vite entry point that mounts the React `App` component onto the root DOM node. 【F:frontend/src/main.tsx†L1-L5】

### frontend/src/api.ts
Centralizes HTTP helpers using Axios for sending initial and continued chat requests and defines shared chat message types for the UI. 【F:frontend/src/api.ts†L1-L34】

### frontend/src/App.tsx
Implements the entire single-page chat client: injects styles, manages conversation state, renders the chat transcript and sidebar resources, and calls backend APIs to continue conversations. 【F:frontend/src/App.tsx†L1-L213】【F:frontend/src/App.tsx†L213-L399】【F:frontend/src/App.tsx†L399-L569】
