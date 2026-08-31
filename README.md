# SIH26100

> **AI-powered Bid Compliance Verification Platform for GeM procurement**

---

## 📌 Phase Overview
**Phase**: `Phase 01 — Project Foundation`

This phase sets up the core architecture, tooling, containerization, and foundational code for the SIH26100 monorepo. It establishes a minimal, clean, and extensible foundation without implementing business logic, authentication, databases, or AI engines prematurely.

---

## 🚀 Current Capabilities
- **FastAPI Backend**: Modular Python 3.12 backend service with CORS, configuration management, and health check endpoints.
- **React + TypeScript Frontend**: Lightweight, responsive Vite-powered frontend interface.
- **Docker Compose**: Containerized multi-service setup for backend and frontend.
- **Environment Configuration**: Robust environment variable handling via `pydantic-settings` and `.env`.
- **Automated Backend Testing**: Unit and endpoint tests using `pytest` and `TestClient`.
- **Modular Monorepo Structure**: Clean architecture preparing for future document extraction, AI agents, and workflow integrations.

---

## 📂 Project Structure

```
SIH26100/
│
├── backend/                  # FastAPI Python backend service
│   ├── app/                  # Application code
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI entrypoint and routes
│   │   ├── config.py         # Configuration using pydantic-settings
│   │   └── api/              # API subpackages & routers (future expansion)
│   │       └── __init__.py
│   ├── tests/                # Backend pytest suite
│   │   ├── __init__.py
│   │   └── test_health.py    # Health & status endpoint tests
│   ├── Dockerfile            # Python 3.12 slim container
│   ├── requirements.txt      # Python dependencies
│   └── .dockerignore
│
├── document_engine/          # Document processing & OCR module (Future Phases)
│   └── .gitkeep
│
├── agents/                   # AI verification & analysis agents (Future Phases)
│   └── .gitkeep
│
├── n8n/                      # n8n workflow integration & nodes (Future Phases)
│   └── .gitkeep
│
├── frontend/                 # React + TypeScript + Vite frontend
│   ├── src/
│   │   ├── App.tsx           # Base application component
│   │   ├── main.tsx          # React application root
│   │   └── index.css         # Clean custom styling
│   ├── public/
│   │   └── .gitkeep
│   ├── Dockerfile            # Node 20 Alpine container
│   ├── .dockerignore
│   ├── package.json          # Node dependencies and scripts
│   ├── package-lock.json
│   ├── tsconfig.json         # TypeScript configuration
│   ├── tsconfig.app.json
│   ├── tsconfig.node.json
│   └── vite.config.ts        # Vite configuration
│
├── database/                 # Database migrations & schemas (Future Phases)
│   └── .gitkeep
│
├── storage/                  # Persistent local document storage
│   └── .gitkeep
│
├── tests/                    # End-to-end and integration tests (Future Phases)
│   └── .gitkeep
│
├── docs/                     # Project documentation
│   └── DEVELOPMENT.md        # Conventions, Git workflows, and coding standards
│
├── .env                      # Local environment configuration (git-ignored)
├── .env.example              # Example environment template
├── .gitignore                # Root git ignore rules
├── docker-compose.yml        # Multi-container orchestration
└── README.md                 # Project documentation
```

---

## 🛠️ Prerequisites

- **Git**
- **Python 3.12+**
- **Node.js 20+** and **npm**
- **Docker Desktop**
- **VS Code** (or preferred IDE)

---

## ⚙️ Environment Configuration

Copy the sample environment file to create your local `.env`:

```bash
cp .env.example .env
```

Key environment variables:
- `APP_NAME`: Application name (`SIH26100`)
- `APP_ENV`: Environment mode (`development`, `production`)
- `BACKEND_HOST`: Host address for FastAPI (`127.0.0.1`)
- `BACKEND_PORT`: Backend port (`8000`)
- `FRONTEND_PORT`: Frontend port (`5173`)
- `DATABASE_URL`: Database connection string (configured in future phases)
- `STORAGE_PATH`: Local storage folder path (`./storage`)

> **Important**: Never commit passwords, secret keys, or credentials to version control.

---

## 💻 Local Development Setup

### 1. Backend Setup (FastAPI)

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (CMD):
.venv\Scripts\activate.bat
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run backend development server
uvicorn app.main:app --reload
```

Accessible URLs:
- **API Status Root**: [http://localhost:8000](http://localhost:8000)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### 2. Frontend Setup (React + Vite)

```bash
# Navigate to frontend directory
cd frontend

# Install node dependencies
npm install

# Start Vite development server
npm run dev
```

Accessible URL:
- **Frontend App**: [http://localhost:5173](http://localhost:5173)

---

## 🧪 Testing

### Backend Unit & Integration Tests

```bash
cd backend
pytest
```

---

## 🐳 Docker Deployment

Run both backend and frontend services using Docker Compose:

```bash
# Build containers
docker compose build

# Start services in foreground (or add -d for background)
docker compose up

# Stop services
docker compose down
```

Services exposed:
- **Backend API**: [http://localhost:8000](http://localhost:8000)
- **Frontend UI**: [http://localhost:5173](http://localhost:5173)

---

## 📐 Development Conventions

Please refer to [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for full details on:
- **Git Branching Strategy**: `main`, `develop`, `feature/*`, `fix/*`
- **Conventional Commits**: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`
- **Coding Standards**: PEP 8 (Python), Strict TypeScript, RESTful API principles
- **Security & Reproducibility**

---

## ✅ Phase 01 Acceptance Criteria

- [x] Project structure created and verified
- [x] FastAPI backend runs cleanly
- [x] `/` root status endpoint operational
- [x] `/health` endpoint operational
- [x] Swagger documentation `/docs` loads
- [x] Pytest backend test suite passes
- [x] React + TypeScript frontend runs on Vite
- [x] TypeScript builds successfully without errors
- [x] Dockerfile configurations for backend and frontend
- [x] Docker Compose multi-service orchestration configured
- [x] `.env` and `.env.example` configured safely
- [x] `.gitignore` comprehensive and verified
- [x] Detailed `README.md` and `docs/DEVELOPMENT.md`
- [x] No secrets or credentials committed
- [x] No Phase 02+ business logic or premature dependencies added
