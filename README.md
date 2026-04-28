# its-ok-gemini

Autonomous AI SDLC agent that can:

- Generate full applications from prompts
- Create and manage GitHub repositories
- Push commits automatically
- Deploy instantly using GitHub Pages
- Revise existing projects through iterative prompts

---

# Core Features

- FastAPI async backend
- Autonomous GitHub automation
- vLLM + Gemini backend support
- RAG-based context retrieval
- Real-time WebSocket logs
- Prometheus metrics
- OpenTelemetry tracing
- Dockerized deployment
- Multi-round code revision pipeline

---

# System Architecture

## High-Level Architecture Tree

```text
its-ok-gemini/
│
├── API Layer
│   ├── FastAPI Server
│   ├── REST Endpoints
│   └── WebSocket Log Streaming
│
├── Orchestration Layer
│   ├── Task Pipeline
│   ├── Background Workers
│   ├── Safety Gates
│   └── Deployment Lifecycle
│
├── LLM Layer
│   ├── vLLM Backend
│   │   ├── DeepSeek-Coder
│   │   └── CodeLlama
│   │
│   └── Gemini Fallback Backend
│
├── RAG Layer
│   ├── Dense Retrieval
│   │   ├── all-MiniLM-L6-v2
│   │   └── Qdrant Vector DB
│   │
│   ├── Sparse Retrieval
│   │   └── BM25
│   │
│   └── Context Chunking Engine
│
├── GitHub Automation
│   ├── Repo Creation
│   ├── Clone & Pull
│   ├── Commit & Push
│   └── GitHub Pages Deployment
│
├── Persistence Layer
│   ├── PostgreSQL
│   ├── SQLAlchemy Async ORM
│   └── Alembic Migrations
│
├── Observability
│   ├── Prometheus Metrics
│   ├── Structured Logging
│   ├── OpenTelemetry Tracing
│   └── Real-Time Logs
│
├── Infrastructure
│   ├── Docker
│   ├── Docker Compose
│   ├── Prometheus
│   └── vLLM Runtime
│
└── Frontend
    ├── Vite + React
    ├── Task Monitoring UI
    └── Live Log Streaming
```

---

## Component Architecture

| Component | Role | Stack |
| :--- | :--- | :--- |
| `FastAPI` | API server and orchestration entrypoint | FastAPI, asyncio |
| `Task Orchestrator` | Handles generation → git → deployment lifecycle | Async Workers |
| `vLLM Service` | Primary local/self-hosted inference backend | vLLM |
| `Gemini Service` | Fallback cloud inference backend | Gemini API |
| `RAG Engine` | Retrieval-augmented context system | Qdrant, SentenceTransformers |
| `GitHub Service` | Repository + deployment automation | GitHub API |
| `GitPython` | Local git operations | GitPython |
| `PostgreSQL` | Persistent task storage | SQLAlchemy |
| `Prometheus` | Metrics collection | Prometheus |
| `WebSocket Logs` | Real-time orchestration monitoring | FastAPI WS |
| `Frontend` | Dashboard and monitoring UI | React, Vite |
| `Docker` | Containerized deployment | Docker |

---

# End-to-End Workflow

## Round 1 — New Project Generation

```text
Task Request
    ↓
Authentication Validation
    ↓
Task Queued
    ↓
LLM Code Generation
    ↓
Repository Creation
    ↓
Files Written
    ↓
Git Commit & Push
    ↓
GitHub Pages Deployment
    ↓
Evaluator Callback
```

---

## Round 2 — Surgical Revision

```text
Existing Repo Clone
    ↓
Read Existing Code
    ↓
Revision Prompt
    ↓
LLM Surgical Update
    ↓
Safety Validation
    ↓
Commit & Push
    ↓
Automatic Redeployment
```

---

# Project Structure

```text
app/
├── api/
│   ├── v1/
│   │   ├── tasks.py
│   │   └── metrics.py
│   └── websocket.py
│
├── core/
│   ├── config.py
│   └── logging.py
│
├── db/
│   └── session.py
│
├── models/
│   ├── base.py
│   └── task.py
│
├── services/
│   ├── github_service.py
│   ├── llm_service.py
│   └── rag_service.py
│
├── workers/
│   └── orchestrator.py
│
└── main.py

frontend/
infra/
migrations/
tests/
```

---

# API Endpoints

| Endpoint | Method | Purpose |
| :--- | :--- | :--- |
| `/api/v1/tasks/ready` | POST | Create generation task |
| `/api/v1/tasks` | GET | Retrieve task history |
| `/metrics` | GET | Prometheus metrics |
| `/ws/logs` | WS | Live log streaming |
| `/health` | GET | Health check |

---

# Models Used

| Model | Role |
| :--- | :--- |
| DeepSeek-Coder-V2 | Primary code generation |
| CodeLlama-70B | Alternate vLLM backend |
| Gemini 2.0 Flash | Cloud fallback |
| all-MiniLM-L6-v2 | Embeddings for RAG |

---

# Infrastructure

| Service | Purpose |
| :--- | :--- |
| Docker | Container runtime |
| Docker Compose | Multi-service orchestration |
| Qdrant | Vector database |
| PostgreSQL | Persistent storage |
| Prometheus | Metrics monitoring |
| vLLM | Local inference serving |

---

# Key Engineering Highlights

- Async-first architecture
- Autonomous deployment pipeline
- LLM backend abstraction
- Graceful RAG degradation
- Structured observability
- GitHub App authentication
- Safety-gated revisions
- Real-time operational visibility

---

# Environment Variables

```env
DATABASE_URL=
DATABASE_SYNC_URL=

GITHUB_USERNAME=
GITHUB_APP_ID=
GITHUB_PRIVATE_KEY_B64=

LLM_BACKEND=
VLLM_ENDPOINT=
VLLM_MODEL=

GEMINI_API_KEY=

QDRANT_URL=
QDRANT_API_KEY=

STUDENT_SECRET=
```

---

# Run Locally

## Backend

```bash
docker compose up --build
```

---

## Frontend

```bash
cd frontend
npm install
npm run dev
```

---

# Tech Stack

- FastAPI
- PostgreSQL
- SQLAlchemy
- Qdrant
- SentenceTransformers
- vLLM
- Gemini API
- GitPython
- Prometheus
- OpenTelemetry
- React
- Docker