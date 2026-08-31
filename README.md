# SIH26100

> **AI-powered Bid Compliance Verification Platform for GeM Procurement**

---

## 📌 Project Overview
**Current Milestone**: `Phase 09 — Compliance Rule Engine`

SIH26100 is an enterprise-grade, deterministic bid compliance and automated procurement verification platform designed for GeM (Government e-Marketplace) tenders. It combines upstream AI-powered intelligence for document interpretation with a strictly deterministic, auditable, and rule-based compliance engine.

### Core Architectural Principle
> **"AI interprets requirements upstream. Deterministic Python rules evaluate them downstream."**
>
> The compliance rule engine operates independently of LLMs (no external AI calls during evaluation). Every evaluation decision produces an explicit, human-readable reason suitable for legal and administrative procurement audit trails.

---

## 🚀 Capabilities

- **Phase 01 — Foundation**: FastAPI modular backend, React + TypeScript + Vite frontend, Docker Compose orchestration.
- **Phase 02 & 03 — Identity & Access**: JWT authentication, RBAC (Bidder, Evaluator, Admin), secure password hashing.
- **Phase 04 & 05 — Tenders & Bidder Management**: Tender RFP lifecycle, GeM bid management, multi-bidder registration.
- **Phase 06 & 07 — Document Engine & Processing**: OCR pipeline (PaddleOCR), PDF extraction, document classification, entity extraction, Supabase storage.
- **Phase 08 — Tender Intelligence & Requirement Normalization**: Clause extraction, currency & time normalization, structured requirement definitions.
- **Phase 09 — Deterministic Compliance Rule Engine**:
  - **Numeric Evaluator**: Exact, inequality, and interval comparisons (`EQUAL`, `NOT_EQUAL`, `GREATER_THAN`, `GREATER_THAN_OR_EQUAL`, `LESS_THAN`, `LESS_THAN_OR_EQUAL`, `MINIMUM`, `MAXIMUM`, `BETWEEN`) with high-precision `Decimal` financial coercion.
  - **Boolean Evaluator**: Strict boolean evaluation with affirmative/negative token normalization.
  - **Date Range Evaluator**: Chronological order, tender deadline validity, and Financial Year intervals (`DATE_EQUAL`, `DATE_BEFORE`, `DATE_AFTER`, `DATE_BETWEEN`, etc.).
  - **Three-Valued Logical Evaluator**: Full Kleene logic for `AND` / `OR` combinations, short-circuiting, and arbitrary nested rule trees (e.g., `A AND (B OR C)`).
  - **Conditional Evaluator**: Deterministic procedural dependencies (`IF <condition> THEN <consequence>`).
  - **Mandatory Document Evaluator**: Presence, candidate matching, verified status confirmation, definitely absent failure, and statutory exemption waivers.
  - **Experience Evaluator**: Cumulative experience years, contract count thresholds, category relevance verification, and completion status filters.
  - **Generic Exemption Mechanism**: Declarative exemption rules (e.g., DPIIT Startup waiver, MSME turnover exemptions) applied without hardcoded tender logic.
  - **Database Integration & Immutability**: PostgreSQL / SQLAlchemy models (`requirements`, `bidder_evidence`, `compliance_results`). Historical evaluations are **never overwritten** to maintain an unbroken audit trail.
  - **Service Architecture**: `API (/api/v1/compliance) ↓ ComplianceService ↓ Rule Engine ↓ PostgreSQL`.

---

## 📂 Project Structure

```
SIH26100/
├── backend/
│   ├── alembic/                      # Database migrations
│   │   └── versions/                 # Revision scripts (including Phase 08 & 09 migrations)
│   ├── app/
│   │   ├── api/v1/endpoints/         # REST API routers (compliance, tenders, bidders, etc.)
│   │   ├── compliance/               # Deterministic Compliance Rule Engine
│   │   │   ├── boolean.py            # Boolean evaluator
│   │   │   ├── conditional.py        # IF/THEN evaluator
│   │   │   ├── dates.py              # Date & timeline evaluator
│   │   │   ├── documents.py          # Document presence & verification evaluator
│   │   │   ├── engine.py             # Central ComplianceEngine coordinator
│   │   │   ├── enums.py              # Statuses, operators, and rule types
│   │   │   ├── exemptions.py         # Exemption mechanism
│   │   │   ├── experience.py         # Track record & contract evaluator
│   │   │   ├── logical.py            # Three-valued AND/OR evaluator
│   │   │   ├── models.py             # Pydantic domain models
│   │   │   └── numeric.py            # Numeric & financial evaluator
│   │   ├── crud/                     # SQLAlchemy data access objects
│   │   ├── models/                   # Declarative database models (compliance, tenders, bidders)
│   │   ├── schemas/                  # Pydantic API schemas
│   │   └── services/                 # Business logic & orchestration services
│   │       └── compliance_service.py # Compliance evaluation service
│   ├── tests/
│   │   ├── compliance/               # 354+ compliance engine unit & integration tests
│   │   └── ...                       # Document, tender, auth, and intelligence test suites
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                         # React + TypeScript Vite frontend
├── docs/                             # Documentation and guides
├── docker-compose.yml
└── README.md
```

---

## 🛠️ Tech Stack

- **Backend**: Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.0, PostgreSQL (Supabase), Alembic
- **Document Processing**: PyMuPDF, PaddleOCR, Pillow
- **Frontend**: React 18, TypeScript, Vite
- **Testing**: pytest (627+ automated unit, integration, and database tests)
- **Containerization**: Docker, Docker Compose

---

## 💻 Local Setup & Execution

### 1. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --port 8000
```

- **Interactive API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative Redoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

- **Frontend Application**: [http://localhost:5173](http://localhost:5173)

---

## 🧪 Testing

Run the comprehensive test suite:

```bash
cd backend

# Run Phase 09 compliance engine tests (354 tests)
pytest tests/compliance/ -v

# Run full repository test suite (627 tests)
pytest tests/ -q
```

---

## 📜 Compliance Engine Contract Scenarios

| Scenario | Requirement | Evidence | Evaluation Result |
| :--- | :--- | :--- | :--- |
| **1. Turnover Above Threshold** | Min turnover ₹15,00,000 | ₹21,00,000 | **`PASS`** |
| **2. Turnover Below Threshold** | Min turnover ₹15,00,000 | ₹8,00,000 | **`FAIL`** |
| **3. Missing Evidence** | Min turnover ₹15,00,000 | Evidence missing / null | **`REVIEW`** |
| **4. Conjunction (Both Pass)** | Turnover $\ge$ 15L **AND** Exp $\ge$ 5 yrs | Both PASS | **`PASS`** |
| **5. Conjunction (One Fails)** | Turnover $\ge$ 15L **AND** Exp $\ge$ 5 yrs | Exp FAIL (< 5 yrs) | **`FAIL`** |
| **6. Disjunction (Pass + Fail)** | ISO 9001 **OR** ISO 14001 | ISO 9001 FAIL, ISO 14001 PASS | **`PASS`** |
| **7. Conditional Requirement** | IF OEM == true THEN Auth == mandatory | OEM = true, Auth = missing | **`FAIL`** |
| **8. Statutory Exemption** | Turnover requirement + Startup waiver | Startup == true | **`EXEMPT`** (passes externally) |
| **9. Uncertain Relevance** | Experience in relevant category | Relevance flag = UNCERTAIN | **`REVIEW`** (no LLM guessing) |

---

## 🔒 Auditability & Immutability

- Every evaluation outputs:
  - `status`: `PASS`, `FAIL`, `REVIEW`, `EXEMPT`, or `NOT_APPLICABLE`
  - `reason`: Deterministic human-readable explanation
  - `evidence_reference`: File name, page, or evidence identifier
  - `actual_value` & `required_value`: Audit snapshots stored in JSONB
  - `evaluated_at`: High-resolution evaluation timestamp
- Historical records in `compliance_results` are strictly immutable and never overwritten.
