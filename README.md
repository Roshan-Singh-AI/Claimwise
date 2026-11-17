# Claimwise

**An explainable insurance-claims workflow built as a personal engineering project.**

Claimwise takes a claim from intake through policy retrieval, risk checks and deterministic settlement calculation. Claims that cross configured thresholds can be reviewed by a human before a decision is recorded. The UI is intentionally small: one workspace, a clear claim register, a guided intake form and a review drawer that exposes the agent trace when needed.

> Demo only. The bundled policies, identities and claims are synthetic. This application is not an insurer system and must not be used to make real coverage or payment decisions.

## Product tour

- **Overview:** claim volume, pending review, calculated payable amount and recent activity.
- **Claims:** searchable claim register with status filtering and a detailed claim record.
- **New claim:** guided intake with policy selection, incident details and invoice line item.
- **Review queue:** human-in-the-loop decisions for claims requiring attention.
- **Policies:** policy records and the clauses used during review.
- **Activity:** hash-chain audit verification and recent events.

## Architecture

```text
React + TypeScript (Vite)
        │ /api proxy
        ▼
FastAPI REST API ───── JWT demo login / role-aware UI
        │
        ▼
LangGraph claim workflow
  1. Intake and structured extraction
  2. Gateway triage
  3. Policy clause retrieval (RAG-style keyword/metadata retrieval)
  4. Risk and fraud signals
  5. Deterministic Decimal settlement calculation
  6. Human-review routing
  7. Decision communication and audit event
        │
        ├── LangChain ChatGroq integration (when GROQ_API_KEY is configured)
        └── SQLite claim state + SHA-256 chained audit events
```

Financial calculations are deterministic Python code. The LLM is not the authority for settlement arithmetic. When no Groq key is configured—or a live model request fails—the current backend uses deterministic fallback behavior so the demo can still be explored offline. The UI exposes the configured model, but **a configured model name is not proof that a specific claim used live Groq inference**; inspect the node trace's `model_used` and `groq_mode` before presenting a live-inference claim.

## Run locally

Requirements: Python 3.11+, Node.js 22.12+, npm.

### 1. Configure the backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add GROQ_API_KEY if you want live Groq inference.
```

Set a unique `CLAIMFORGE_JWT_SECRET` before exposing the app beyond localhost. The seeded accounts and passwords are for local demonstration only.

### 2. Start the API

```bash
PYTHONPATH=backend uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### 3. Start the React app

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The Vite dev server proxies `/api` to `http://localhost:8000`.

### 4. Demo personas

Use the role buttons on the sign-in screen. These are seeded demo identities, not production accounts:

| Role | Email | Password |
|---|---|---|
| Claims officer | `roshan@claimwise.demo` | `DemoOfficer@2026` |
| Policyholder | `asha.rao@example.in` | `Policy@2026` |
| SIU investigator | `priya@claimwise.demo` | `SIU@2026` |

## Run with Docker Compose

```bash
cp .env.example .env
# Add GROQ_API_KEY if desired and replace the demo JWT secret.
docker compose up --build
```

- React workspace: http://localhost:5173
- FastAPI docs: http://localhost:8000/docs
- SQLite data is persisted in the `claimwise-data` Docker volume.

## Tests

```bash
PYTHONPATH=backend python -m unittest discover -s backend/tests -v
PYTHONPATH=backend python -m app.evals.eval_runner
```

The bundled backend suite currently covers login/JWT helpers, representative graph outcomes, human-review resume, audit-chain integrity, the golden evaluation set and HTTP-level API flows (login → authorized claim access → submission → fetch → audit). These are **API-level tests**, not browser-level end-to-end tests. In the environment used to prepare this archive, the LangGraph and Groq packages were not installed, so backend tests exercised the built-in compatibility graph and deterministic inference fallback. A full dependency install and a configured Groq key are required to validate the native LangGraph + live Groq path. Install frontend dependencies and run `npm run build` to type-check and build the React application; that build could not be run in this environment because npm package installation timed out.

## Dependency snapshot (checked 17 Nov 2026)

| Package | Version | Source |
|---|---:|---|
| React / React DOM | 19.3.1 | [npm](https://www.npmjs.com/package/react) |
| Vite | 8.3.8 | [npm](https://www.npmjs.com/package/vite) |
| `@vitejs/plugin-react` | 6.3.0 | [npm](https://www.npmjs.com/package/@vitejs/plugin-react) |
| TypeScript | 7.0.2 | [npm](https://www.npmjs.com/package/typescript) |
| LangGraph | 1.2.22 | [PyPI](https://pypi.org/project/langgraph/) |
| LangChain | 1.5.0 | [PyPI](https://pypi.org/project/langchain/) |
| `langchain-core` | 1.8.1 | [PyPI](https://pypi.org/project/langchain-core/) |
| `langchain-groq` | 1.2.0 | [PyPI](https://pypi.org/project/langchain-groq/) |
| Groq Python SDK | 1.7.0 | [PyPI](https://pypi.org/project/groq/) |
| FastAPI | 0.163.1 | [PyPI](https://pypi.org/project/fastapi/) |
| Pydantic | 2.14.3 | [PyPI](https://pypi.org/project/pydantic/) |

This is a dated dependency snapshot, not a promise that these remain the latest versions. Re-check registries before upgrading or deploying.

## Open-source references reviewed

These projects informed the workflow and feature selection; Claimwise is an independent implementation, not a fork:

- [AWS sample — agentic insurance claims processing on EKS](https://github.com/aws-samples/sample-agentic-insurance-claims-processing-eks): multi-agent workflow and human review patterns.
- [AWS sample — multi-agent life insurance claims demo](https://github.com/aws-samples/sample-agentic-insurance-claims-processing-demo): specialist agents for identity, documents, policy validation and fraud review.
- [VinitMetange — AI insurance claims agent](https://github.com/VinitMetange/ai-insurance-claims-agent): LangGraph, RAG and claim-processing orchestration.
- [sap156 — AI claims agent with LangGraph](https://github.com/sap156/ai-claims-agent-langgraph): risk and validity workflow separation.
- [aqwenaaa — AXA Prism](https://github.com/aqwenaaa/axa-prism): claims workbench and review-oriented product navigation.

## Important demo limitations to address before production

- The seeded users and fixed demo credentials must be replaced.
- The fallback JWT secret must be replaced with a strong secret; add secret rotation, refresh-token handling, secure cookie/token storage and login rate limiting.
- Server-side role guards and policyholder ownership checks are implemented for the current claim, policy, review, audit and evaluation routes. Complete a dedicated security review before production use; the demo personas are not an identity-management system.
- Add upload storage, malware scanning, OCR/document extraction, real policy document ingestion and provenance before claiming document-level automation.
- The current policy retriever is lightweight keyword/metadata retrieval, not a production vector database pipeline.
- Add browser E2E tests (e.g. Playwright), API contract tests and a real Groq integration test with a configured key before claiming complete E2E verification.
- Review policy logic with a qualified insurance domain expert; the sample policy data and arithmetic are illustrative.
