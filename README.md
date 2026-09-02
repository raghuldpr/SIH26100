# SIH26100 — Quixotic Bid Compliance Platform

> **Enterprise-Grade AI & Deterministic Multi-Agent Bid Compliance Verification Platform for GeM Procurement**

---

## 📌 Platform Overview

**SIH-26100** is an automated procurement bid compliance and verification system designed for the Government e-Marketplace (GeM). It integrates deterministic document parsing, structured parameter extraction, an immutable audit trail, and an n8n-orchestrated 10-agent verification workflow powered by server-side Groq LLaMA-3.3-70B minimal semantic fallback.

### Core Architectural Principle
> **"Deterministic rules, OCR, and document forensics evaluate compliance first. AI/LLMs are strictly restricted upstream for ambiguous clause interpretation via a hardened AI Gateway."**

---

## 🏛️ System Architecture

```
[Web Browser Client]
       │
       ▼ (HTTPS / Port 5173 / Port 80)
[React + TypeScript + Vite Frontend] (Stitch Design System, Tailwind CSS)
       │
       ▼ (REST API / Bearer JWT / Port 8000)
[FastAPI Backend Application]
       │
       ├─► [PostgreSQL / Supabase Database] (SQLAlchemy 2.0 + Connection Pooling)
       ├─► [Supabase Storage / Local Volume] (Document Vault & Pre-Signed Signed URLs)
       ├─► [Document Engine Microservice (Port 8001)] (PyMuPDF / Tesseract / OpenCV)
       ├─► [AI Gateway] ──► [Groq LLaMA-3.3-70B] (Server-side minimal semantic fallback)
       └─► [n8n Multi-Agent Orchestrator (Port 5678)]
                 │
                 ├─► 1. Tender Intelligence Agent
                 ├─► 2. GST Verification Agent
                 ├─► 3. PAN Verification Agent
                 ├─► 4. Udyam Verification Agent
                 ├─► 5. Financial Verification Agent
                 ├─► 6. Experience Eligibility Agent
                 ├─► 7. Document Forensics Agent
                 ├─► 8. Entity Resolution Agent
                 ├─► 9. Risk Intelligence Agent
                 └─► 10. Final Compliance Aggregation Agent
```

---

## 📂 Repository Structure

```
SIH26100/
├── backend/                  # FastAPI REST Backend application
│   ├── alembic/              # Database migration versions
│   ├── app/
│   │   ├── api/v1/           # API endpoints (auth, tenders, bidders, documents, verification, health)
│   │   ├── compliance/       # Deterministic rule evaluation engine
│   │   ├── core/             # Security, database, storage, validation
│   │   ├── crud/             # Database access operations
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic validation schemas
│   │   └── services/         # Verification aggregator, n8n client, AI Gateway
│   ├── tests/                # Unit, integration, Phase 11 & Phase 12 test suites
│   ├── Dockerfile            # Backend container specification
│   └── requirements.txt      # Python dependencies
├── document-engine/          # High-throughput OCR & document extraction microservice
│   ├── app/                  # Classifiers, extractors, OCR pipeline
│   ├── tests/                # 90 automated document engine tests
│   ├── Dockerfile            # Document Engine container with Tesseract OCR
│   └── requirements.txt      # OCR & extraction dependencies
├── frontend/                 # React 18 + TypeScript + Vite + Tailwind CSS
│   ├── src/
│   │   ├── api/              # Typed API clients (auth, tenders, bidders, documents, verification, health)
│   │   ├── components/       # Stitch UI primitives, tender, bidder, verification, document components
│   │   ├── context/          # AuthContext with Bearer JWT lifecycle
│   │   ├── layouts/          # AppLayout, Sidebar, Header
│   │   ├── pages/            # Dashboard, Tenders, Bidders, Documents, Verification, Reports, Settings
│   │   ├── routes/           # ProtectedRoute, PublicRoute, AppRoutes
│   │   └── types/            # TypeScript domain interfaces
│   ├── Dockerfile            # Frontend container specification
│   └── package.json          # Node dependencies
├── n8n/                      # 11 Production Multi-Agent workflow definitions (JSON)
├── docker-compose.yml        # Production multi-container orchestration
├── .env.example              # Master environment configuration template
└── README.md
```

---

## ⚙️ Environment Configuration

Copy `.env.example` to `.env` in the repository root and configure your credentials:

```bash
cp .env.example .env
```

### Essential Environment Variables

| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `DATABASE_URL` | PostgreSQL / Supabase connection string | `postgresql://postgres:postgres@localhost:5432/sih26100_db` |
| `JWT_SECRET_KEY` | Cryptographic secret for signing Bearer JWTs | `change-this-to-a-secure-random-256-bit-key` |
| `SUPABASE_URL` | Supabase project URL | `https://[PROJECT-REF].supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY`| Supabase service role key | `[YOUR-SERVICE-ROLE-KEY]` |
| `GROQ_API_KEY` | Server-side Groq API key for AI Gateway | `gsk_[YOUR-GROQ-API-KEY]` |
| `GROQ_MODEL` | Server-side LLM model | `llama-3.3-70b-versatile` |
| `N8N_WEBHOOK_URL` | n8n verification webhook dispatch URL | `http://localhost:5678/webhook/sih26100/bid-verification` |
| `DOCUMENT_ENGINE_URL` | Internal Document Engine microservice URL | `http://localhost:8001` |
| `VITE_API_BASE_URL` | Public frontend API entry point | `http://localhost:8000/api/v1` |

---

## 🚀 Running with Docker Compose

Start the complete multi-service stack with a single command:

```bash
docker compose up -d
```

### Services Started:
- **Frontend**: [http://localhost:5173](http://localhost:5173)
- **FastAPI Backend**: [http://localhost:8000](http://localhost:8000) (Interactive Docs: `/docs`)
- **Document Engine**: [http://localhost:8001](http://localhost:8001) (Health: `/health`)
- **n8n Orchestration** *(optional profile)*: `docker compose --profile orchestration up -d` ([http://localhost:5678](http://localhost:5678))

---

## 💻 Local Development Execution

### 1. Backend Application

```bash
cd backend
python -m venv .venv
# Activate virtualenv (Windows: .venv\Scripts\Activate.ps1 | Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### 2. Document Engine Microservice

```bash
cd document-engine
python -m venv .venv
# Activate virtualenv
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

### 3. Frontend Application

```bash
cd frontend
npm install
npm run dev
```

---

## 🧪 Automated Testing & Verification

Run the full automated test suite:

```bash
# Phase 11 Regression Suite (83 tests)
$env:PYTHONPATH="backend;document-engine;."; python -m unittest discover -s backend/tests -p "test_*_phase11.py"

# Phase 12 Multi-Agent Verification Suite (115 tests)
$env:PYTHONPATH="backend;document-engine;."; python -m unittest discover -s backend/tests -p "test_phase12_*.py"

# Frontend Production Build (TypeScript + Vite)
npm run build
```

---

## 🔒 Security & Provenance Assurances

1. **Deterministic Processing First**: No LLM calls during document extraction or compliance rules evaluation.
2. **Server-Side AI Gateway**: Groq keys are never exposed to client browsers or bundled in frontend assets.
3. **Cryptographic SHA-256 Hashes**: Every document artifact and verification response outputs an immutable anti-tamper digest.
4. **Pre-Signed Storage URLs**: Documents are downloaded strictly through time-limited pre-signed URLs with role-based access control.
5. **No Dangerous DOM Operations**: Audited for zero occurrences of `dangerouslySetInnerHTML`, `innerHTML`, or client-side eval.
