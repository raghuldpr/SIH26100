# SIH-26100 Document Engine Service

Standalone, high-throughput Python microservice designed for deterministic document extraction, OCR, classification, and structured attribute parsing across procurement documents.

---

## 🏛️ Architecture Overview

The Document Engine functions as a dedicated microservice in the hybrid SIH-26100 system:

```
[React Frontend]
       │
       ▼ (User uploads document)
[FastAPI Backend (Port 8000)]
       │
       ▼ (Forwards file stream)
[Document Engine (Port 8001)] ◄─── (Direct call) ─── [n8n Workflow Engine]
       │
       ├─► File validation (PDF & Image MIME validation)
       ├─► Native text extraction (PyMuPDF)
       ├─► Scanned OCR rendering + OpenCV preprocessing + OCR
       ├─► Table extraction (pdfplumber)
       ├─► Deterministic classification (8 types)
       ├─► Structured information extraction
       ▼
[Standardized Structured JSON Response]
       │
       ▼
[n8n Workflow Orchestrator]
       │
       ▼
[Compliance, Entity, and Fraud Detection Agents]
```

### Core Design Principles
- **Strictly Deterministic**: No LLMs or Gemini calls in this service. Uses regex, keyword proximity, and rule-based heuristics.
- **Stateless**: Does not permanently store documents inside the container. Temporary files are stored in scratch directories and cleaned up immediately in `finally` blocks.
- **Non-Destructive**: Original uploaded documents are never modified.

---

## 🚀 Running the Service

### Option A: Local Development (Python)

Ensure Python 3.12+ is installed:

```bash
cd document-engine

# Create & activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start service with hot reload
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

The API docs are available at `http://localhost:8001/docs`.

### Option B: Docker Container

```bash
# Build the Docker image
docker build -t sih26100-document-engine:latest document-engine/

# Run the container
docker run -d \
  --name sih26100-document-engine \
  -p 8001:8001 \
  -e PORT=8001 \
  -e MAX_UPLOAD_SIZE_MB=25 \
  sih26100-document-engine:latest
```

### Option C: Docker Compose

From the repository root:

```bash
docker compose up -d document-engine
```

---

## ⚙️ Environment Variables

Copy `.env.example` to `.env` to configure:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `PORT` | `8001` | Service listening port |
| `HOST` | `0.0.0.0` | Binding interface |
| `APP_ENV` | `production` | Environment mode (`development`, `staging`, `production`) |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `TEMP_DIR` | `/app/temp` | Temporary processing scratch path |
| `MAX_UPLOAD_SIZE_MB` | `25` | Maximum allowed file upload size |
| `CORS_ORIGINS` | `*` | Allowed CORS origins (comma-separated) |

---

## 📡 API Reference

### 1. Health & Discovery

#### `GET /health`
Returns service operational health.
```json
{
  "status": "healthy",
  "service": "document-engine",
  "version": "1.0.0",
  "environment": "production"
}
```

#### `GET /api/v1/info`
Returns service metadata and capabilities.

---

### 2. Unified Document Pipeline

#### `POST /api/v1/documents/process`
Accepts a PDF or image multipart file upload and processes it through the complete pipeline.

**Request**:
- Content-Type: `multipart/form-data`
- Field: `file` (Binary document)

**Response**:
```json
{
  "document_id": "4b6dfdf9-0db9-4670-8b1e-b83e0a174092",
  "filename": "GST_Certificate.pdf",
  "document_type": "GST",
  "classification_confidence": 0.98,
  "pages": 1,
  "extraction": {
    "method": "native_pdf",
    "ocr_used": false,
    "text": "Government of India\nRegistration Certificate\n...",
    "pages": [
      {
        "page_number": 1,
        "text": "Government of India\nRegistration Certificate\n...",
        "character_count": 248
      }
    ]
  },
  "tables": [
    {
      "page": 1,
      "table_index": 0,
      "rows": [
        ["Particulars", "Details"],
        ["Jurisdiction", "Ward 105, Mumbai"]
      ]
    }
  ],
  "data": {
    "gstin": "27ABCDE1234F1Z5",
    "company_name": "ACME INFOTECH",
    "legal_name": "ACME GLOBAL INFOTECH PRIVATE LIMITED",
    "status": "Active"
  },
  "processing": {
    "status": "completed",
    "processing_time_ms": 42,
    "error_code": null,
    "message": "Document successfully processed."
  }
}
```

---

## 🔌 Integration Guides

### Integration with FastAPI Backend (`backend/`)

The existing FastAPI backend forwards uploaded documents to the Document Engine:

```python
import httpx
from pathlib import Path

DOCUMENT_ENGINE_URL = "http://document-engine:8001"  # Inside Docker network

async def process_with_document_engine(file_path: Path, filename: str) -> dict:
    """Streams a stored document to the Document Engine service."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        with open(file_path, "rb") as f:
            response = await client.post(
                f"{DOCUMENT_ENGINE_URL}/api/v1/documents/process",
                files={"file": (filename, f, "application/pdf")},
            )
            response.raise_for_status()
            return response.json()
```

---

### Integration with n8n Workflows

n8n can orchestrate document ingestion by calling the Document Engine with an **HTTP Request** node:

```
[Trigger / File Upload]
          │
          ▼
   [HTTP Request Node]
          │  Method: POST
          │  URL: http://document-engine:8001/api/v1/documents/process
          │  Send Body: Form-Data (Multipart)
          │  Body Parameters:
          │    - Parameter Type: Form Binary Data
          │    - Name: file
          │    - Input Data Field Name: data
          │
          ▼
 [Structured JSON Output]
          │  {{ $json.document_type }}
          │  {{ $json.data.gstin }}
          │  {{ $json.data.company_name }}
          ▼
[Downstream Rule / Agent Nodes]
```

#### Sample n8n Node JSON Configuration:
```json
{
  "parameters": {
    "method": "POST",
    "url": "http://document-engine:8001/api/v1/documents/process",
    "sendBinaryData": true,
    "binaryPropertyName": "data:file",
    "options": {
      "timeout": 60000
    }
  },
  "name": "Process Document",
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.2
}
```

---

## 🧪 Testing

Execute the comprehensive test suite:

```bash
# Run all 90 tests
pytest tests/ -v

# Run comprehensive validation suite across all 8 document types & edge cases
python scripts/run_phase07_validation.py
```
