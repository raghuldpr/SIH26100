import json
import subprocess
from pathlib import Path

arch = {
    "schema_version": 1,
    "diagram_type": "architecture",
    "meta": {
        "title": "TenderTrust — Reliable Procurement Decisions Architecture",
        "subtitle": "AI-Assisted GeM Bid Compliance Verification Platform with Deterministic-First Engine & Human Governance",
        "output": "tendertrust_architecture.html",
        "quality_profile": "showcase",
        "viewBox": [1760, 990],
        "views": [
            {
                "id": "full-platform-flow",
                "label": "Full Platform Flow",
                "focus": [
                    "officer", "frontend_ui", "fastapi_app", "db_postgres", 
                    "storage_vault", "n8n_engine", "rule_engine", "evidence_aggregator", "officer_final"
                ],
                "note": "Complete procurement verification lifecycle from intake through deterministic evaluation to final officer decision."
            },
            {
                "id": "deterministic-verification",
                "label": "Deterministic-First Engine",
                "focus": [
                    "doc_pipeline", "statutory_engine", "financial_engine", 
                    "forensics_engine", "rule_engine", "evidence_aggregator"
                ],
                "note": "Strict rule-based verification: statutory identity, financial arithmetic (Sum÷N), forensics, and zero-LLM compliance."
            },
            {
                "id": "ai-gateway-escalation",
                "label": "Controlled AI Gateway Path",
                "focus": [
                    "rule_engine", "ai_gateway", "openrouter_api", "evidence_aggregator"
                ],
                "note": "Bounded escalation for ambiguous clauses via OpenRouter API through guarded, schema-enforcing AI Gateway."
            },
            {
                "id": "human-governance",
                "label": "Human Decision Authority",
                "focus": [
                    "evidence_aggregator", "officer_final", "frontend_console", "officer"
                ],
                "note": "AI provides advisory signals; final legal qualification remains exclusively with the Procurement Officer."
            }
        ]
    },
    "components": [
        # Column 1: Users, Presentation & Final Decision (Left: X=60..240)
        {
            "id": "officer",
            "type": "external",
            "label": "Procurement Officer",
            "sublabel": "Tender Authority",
            "tag": "Final Authority",
            "pos": [60, 50],
            "size": [180, 64]
        },
        {
            "id": "frontend_ui",
            "type": "frontend",
            "label": "TenderTrust Web UI",
            "sublabel": "React 18 + TailwindCSS",
            "tag": "Implemented",
            "brand": "react",
            "pos": [60, 180],
            "size": [180, 64]
        },
        {
            "id": "frontend_console",
            "type": "frontend",
            "label": "Compliance Console",
            "sublabel": "Evidence & Audit Views",
            "tag": "Implemented",
            "pos": [60, 310],
            "size": [180, 64]
        },
        {
            "id": "officer_final",
            "type": "security",
            "label": "Officer Decision Console",
            "sublabel": "Qualify / Disqualify / Review",
            "tag": "Human Authority",
            "pos": [60, 750],
            "size": [190, 66]
        },

        # Column 2: Governance, API Services & Aggregation (Mid-Left: X=320..500)
        {
            "id": "committee",
            "type": "external",
            "label": "Tender Committee",
            "sublabel": "Verification & Audit",
            "tag": "Human Oversight",
            "pos": [320, 50],
            "size": [180, 64]
        },
        {
            "id": "fastapi_app",
            "type": "backend",
            "label": "FastAPI Core Backend",
            "sublabel": "REST APIs & Validation",
            "tag": "Implemented",
            "brand": "fastapi",
            "pos": [320, 180],
            "size": [180, 64]
        },
        {
            "id": "auth_service",
            "type": "security",
            "label": "Auth & RBAC Security",
            "sublabel": "JWT (HS256) & Isolation",
            "tag": "Implemented",
            "pos": [320, 310],
            "size": [180, 64]
        },
        {
            "id": "evidence_aggregator",
            "type": "backend",
            "label": "Evidence & Risk Aggregator",
            "sublabel": "Scores, Citations & Hashes",
            "tag": "Implemented",
            "pos": [320, 750],
            "size": [190, 66]
        },

        # Column 3: Storage & Core Rule Engine (Center: X=580..780)
        {
            "id": "db_postgres",
            "type": "database",
            "label": "PostgreSQL Database",
            "sublabel": "Tenders, Bids & Audits",
            "tag": "Implemented",
            "brand": "postgresql",
            "pos": [580, 180],
            "size": [180, 64]
        },
        {
            "id": "storage_vault",
            "type": "database",
            "label": "Private Document Store",
            "sublabel": "Supabase Object Vault",
            "tag": "Implemented",
            "brand": "supabase",
            "pos": [580, 310],
            "size": [180, 64]
        },
        {
            "id": "rule_engine",
            "type": "backend",
            "label": "Compliance Rules Engine",
            "sublabel": "Evaluators (Zero LLM)",
            "tag": "Deterministic Core",
            "pos": [580, 520],
            "size": [190, 66]
        },

        # Column 4: Orchestration, Deterministic Verifiers & AI Gateway (Mid-Right: X=880..1070)
        {
            "id": "n8n_engine",
            "type": "messagebus",
            "label": "n8n Orchestrator",
            "sublabel": "Multi-Agent Coordinator",
            "tag": "Implemented",
            "pos": [880, 180],
            "size": [190, 64]
        },
        {
            "id": "statutory_engine",
            "type": "backend",
            "label": "Statutory ID Verifier",
            "sublabel": "GSTIN / PAN / Udyam",
            "tag": "Deterministic Engine",
            "pos": [880, 410],
            "size": [190, 64]
        },
        {
            "id": "financial_engine",
            "type": "backend",
            "label": "Financial & Exp Verifier",
            "sublabel": "Avg Turnover & Work Orders",
            "tag": "Deterministic Engine",
            "pos": [880, 520],
            "size": [190, 64]
        },
        {
            "id": "forensics_engine",
            "type": "security",
            "label": "Document Forensics",
            "sublabel": "Similarity & Anomaly",
            "tag": "Deterministic Engine",
            "pos": [880, 630],
            "size": [190, 64]
        },
        {
            "id": "ai_gateway",
            "type": "security",
            "label": "Controlled AI Gateway",
            "sublabel": "Ambiguity Guard & Schema",
            "tag": "Implemented",
            "pos": [880, 750],
            "size": [190, 66]
        },

        # Column 5: External Gateways, Intake & Adapters (Right: X=1220..1420)
        {
            "id": "gem_portal",
            "type": "cloud",
            "label": "GeM Portal (India)",
            "sublabel": "Government e-Marketplace",
            "tag": "Implemented Intake",
            "pos": [1220, 50],
            "size": [190, 64]
        },
        {
            "id": "doc_pipeline",
            "type": "backend",
            "label": "Document Intake Engine",
            "sublabel": "PDF/DOCX/OCR/SHA-256",
            "tag": "Implemented",
            "pos": [1220, 180],
            "size": [190, 64]
        },
        {
            "id": "gov_adapters",
            "type": "cloud",
            "label": "Govt Verification Adapters",
            "sublabel": "GST/ITR/MSME/MCA21/EPFO",
            "tag": "Planned Adapters",
            "pos": [1220, 520],
            "size": [190, 66]
        },
        {
            "id": "openrouter_api",
            "type": "cloud",
            "label": "OpenRouter API",
            "sublabel": "Target AI Provider",
            "tag": "Planned Integration",
            "pos": [1220, 750],
            "size": [190, 66]
        }
    ],
    "boundaries": [
        {
            "kind": "region",
            "label": "Presentation Layer (React 18 & Vite)",
            "wraps": ["frontend_ui", "frontend_console"],
            "pad": 18
        },
        {
            "kind": "region",
            "label": "Application & API Layer (FastAPI Backend)",
            "wraps": ["fastapi_app", "auth_service"],
            "pad": 18
        },
        {
            "kind": "security-group",
            "label": "Isolated State & Storage Vault",
            "wraps": ["db_postgres", "storage_vault"],
            "pad": 18
        },
        {
            "kind": "region",
            "label": "Deterministic Verification Services (Zero LLM)",
            "wraps": ["statutory_engine", "financial_engine", "forensics_engine", "rule_engine"],
            "pad": 22
        },
        {
            "kind": "security-group",
            "label": "Controlled AI Gateway & Target Provider",
            "wraps": ["ai_gateway", "openrouter_api"],
            "pad": 18
        },
        {
            "kind": "security-group",
            "label": "Evidence Assessment & Statutory Officer Authority",
            "wraps": ["evidence_aggregator", "officer_final"],
            "pad": 18
        }
    ],
    "connections": [
        # Officers to Frontend
        {
            "id": "c_officer_ui",
            "from": "officer",
            "to": "frontend_ui",
            "label": "HTTPS Access",
            "variant": "emphasis",
            "labelDy": 24
        },
        {
            "id": "c_committee_console",
            "from": "committee",
            "to": "frontend_console",
            "label": "Audit Review",
            "variant": "default",
            "fromSide": "left",
            "toSide": "top",
            "via": [[280, 82], [280, 280], [150, 280]]
        },
        # Frontend to Backend
        {
            "id": "c_ui_api",
            "from": "frontend_ui",
            "to": "fastapi_app",
            "label": "REST API :8000",
            "variant": "emphasis"
        },
        {
            "id": "c_console_api",
            "from": "frontend_console",
            "to": "fastapi_app",
            "label": "Audit APIs",
            "variant": "default",
            "fromSide": "right",
            "toSide": "bottom"
        },
        {
            "id": "c_auth_validate",
            "from": "auth_service",
            "to": "fastapi_app",
            "label": "RBAC / JWT Check",
            "variant": "security",
            "fromSide": "top",
            "toSide": "bottom",
            "labelDy": -20
        },
        # GeM Intake to Doc Pipeline
        {
            "id": "c_gem_intake",
            "from": "gem_portal",
            "to": "doc_pipeline",
            "label": "NIT & Bid Intake",
            "variant": "emphasis",
            "labelDy": 24
        },
        # Backend to Storage & DB
        {
            "id": "c_api_db",
            "from": "fastapi_app",
            "to": "db_postgres",
            "label": "Asyncpg / SQL",
            "variant": "default"
        },
        {
            "id": "c_api_vault",
            "from": "fastapi_app",
            "to": "storage_vault",
            "label": "Private Docs",
            "variant": "security",
            "fromSide": "bottom",
            "toSide": "left",
            "via": [[410, 342]]
        },
        # Backend to n8n Orchestrator (via top channel to avoid db_postgres)
        {
            "id": "c_api_n8n",
            "from": "fastapi_app",
            "to": "n8n_engine",
            "label": "Webhook Trigger",
            "variant": "emphasis",
            "fromSide": "top",
            "toSide": "top",
            "via": [[410, 138], [975, 138]]
        },
        # n8n to Doc Pipeline
        {
            "id": "c_n8n_doc",
            "from": "n8n_engine",
            "to": "doc_pipeline",
            "label": "Process Jobs",
            "variant": "default"
        },
        # Doc Pipeline to Verifiers (via right side channel)
        {
            "id": "c_doc_stat",
            "from": "doc_pipeline",
            "to": "statutory_engine",
            "label": "Statutory Docs",
            "variant": "default",
            "fromSide": "bottom",
            "toSide": "right",
            "via": [[1315, 442]]
        },
        {
            "id": "c_doc_fin",
            "from": "doc_pipeline",
            "to": "financial_engine",
            "label": "Financial Statements",
            "variant": "default",
            "fromSide": "bottom",
            "toSide": "right",
            "via": [[1315, 552]]
        },
        {
            "id": "c_doc_forensic",
            "from": "doc_pipeline",
            "to": "forensics_engine",
            "label": "Extracted Layouts",
            "variant": "default",
            "fromSide": "bottom",
            "toSide": "right",
            "via": [[1315, 662]]
        },
        # Verifiers flow to Rule Engine (direct leftward horizontal connections)
        {
            "id": "c_stat_rule",
            "from": "statutory_engine",
            "to": "rule_engine",
            "label": "Verified Identity",
            "variant": "default",
            "fromSide": "left",
            "toSide": "top",
            "via": [[830, 442], [830, 490], [675, 490]]
        },
        {
            "id": "c_fin_rule",
            "from": "financial_engine",
            "to": "rule_engine",
            "label": "Turnover Proof",
            "variant": "default",
            "fromSide": "left",
            "toSide": "right"
        },
        {
            "id": "c_forensic_rule",
            "from": "forensics_engine",
            "to": "rule_engine",
            "label": "Similarity Signals",
            "variant": "default",
            "fromSide": "left",
            "toSide": "bottom",
            "via": [[830, 662], [830, 610], [675, 610]]
        },
        # Govt Adapters to Financial/Statutory Engine (Planned)
        {
            "id": "c_gov_stat",
            "from": "gov_adapters",
            "to": "statutory_engine",
            "label": "Govt Registries",
            "variant": "dashed",
            "fromSide": "top",
            "toSide": "bottom",
            "via": [[1315, 480], [975, 480]]
        },
        # Rule Engine to AI Gateway (Escalation only)
        {
            "id": "c_rule_ai",
            "from": "rule_engine",
            "to": "ai_gateway",
            "label": "Ambiguity Escalation",
            "variant": "security",
            "fromSide": "bottom",
            "toSide": "top",
            "via": [[675, 715], [975, 715]]
        },
        # AI Gateway to OpenRouter API (Planned - direct horizontal rightward)
        {
            "id": "c_ai_openrouter",
            "from": "ai_gateway",
            "to": "openrouter_api",
            "label": "JSON Semantic Prompt",
            "variant": "dashed"
        },
        # Rule Engine to Evidence Aggregator (downward into aggregation)
        {
            "id": "c_rule_evidence",
            "from": "rule_engine",
            "to": "evidence_aggregator",
            "label": "Compliance Results",
            "variant": "emphasis",
            "fromSide": "bottom",
            "toSide": "top",
            "via": [[675, 680], [415, 680]]
        },
        # Evidence to Officer Final Review (direct leftward horizontal)
        {
            "id": "c_evidence_officer",
            "from": "evidence_aggregator",
            "to": "officer_final",
            "label": "Citations & Scores",
            "variant": "emphasis"
        },
        # Officer Final back to UI (upward channel on the left)
        {
            "id": "c_officer_verdict",
            "from": "officer_final",
            "to": "frontend_console",
            "label": "Officer Decision",
            "variant": "security",
            "fromSide": "top",
            "toSide": "bottom",
            "labelDy": -20
        }
    ],
    "cards": [
        {
            "dot": "emerald",
            "title": "Deterministic-First Principle",
            "items": [
                "Parsers, OCR, format checks, and turnover arithmetic execute before any AI escalation",
                "Compliance Rules Engine runs pure deterministic evaluators with zero LLM dependencies",
                "Average Turnover calculation: Sum of Eligible Yearly Turnovers ÷ Number of Eligible Years"
            ]
        },
        {
            "dot": "cyan",
            "title": "Controlled AI Gateway (OpenRouter)",
            "items": [
                "OpenRouter API is the planned external AI provider; accessed strictly through controlled AI Gateway",
                "AI provides semantic clause interpretation only; no direct qualification or disqualification decisions",
                "Data minimization enforced: only necessary anonymized text is dispatched with Pydantic validation"
            ]
        },
        {
            "dot": "rose",
            "title": "Human Authority & Governance",
            "items": [
                "AI-assisted decision support only: final qualification decision remains with the Procurement Officer",
                "Decision Logic: Mandatory Failed -> NOT QUALIFIED | Missing/Unclear Evidence -> MANUAL REVIEW",
                "Every assessment is anchored to immutable SHA-256 document hashes, page numbers, and audit logs"
            ]
        }
    ]
}

out_path = Path("tendertrust_architecture.architecture.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(arch, f, indent=2)

print(f"Written {out_path}")
