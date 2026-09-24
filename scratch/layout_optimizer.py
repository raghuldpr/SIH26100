import json
import subprocess
from pathlib import Path

def build_architecture():
    # 1760 x 990 16:9 Presentation Layout
    # Grid columns:
    # Col 1: Users & Final Decision (X=70)
    # Col 2: Presentation Layer (X=320)
    # Col 3: Application & Security Layer (X=580)
    # Col 4: Storage & Core Rule Engine (X=840)
    # Col 5: Specialized Deterministic Verifiers (X=1120)
    # Col 6: Intake, Orchestration & External (X=1430)

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
            # -----------------------------------------------------------------
            # TOP ROW: USERS & EXTERNAL ENTRY POINTS (Y=50)
            # -----------------------------------------------------------------
            {
                "id": "officer",
                "type": "external",
                "label": "Procurement Officer",
                "sublabel": "Tender Authority",
                "tag": "Final Authority",
                "pos": [70, 50],
                "size": [180, 64]
            },
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
                "id": "gem_portal",
                "type": "cloud",
                "label": "GeM Portal (India)",
                "sublabel": "Government e-Marketplace",
                "tag": "Implemented Intake",
                "pos": [1430, 50],
                "size": [190, 64]
            },

            # -----------------------------------------------------------------
            # ROW 2: PRESENTATION & APPLICATION SERVICES (Y=180)
            # -----------------------------------------------------------------
            {
                "id": "frontend_ui",
                "type": "frontend",
                "label": "TenderTrust Web UI",
                "sublabel": "React 18 + TailwindCSS",
                "tag": "Implemented",
                "brand": "react",
                "pos": [70, 180],
                "size": [180, 64]
            },
            {
                "id": "frontend_console",
                "type": "frontend",
                "label": "Compliance Console",
                "sublabel": "Evidence & Audit Views",
                "tag": "Implemented",
                "pos": [320, 180],
                "size": [180, 64]
            },
            {
                "id": "fastapi_app",
                "type": "backend",
                "label": "FastAPI Core Backend",
                "sublabel": "REST APIs & Validation",
                "tag": "Implemented",
                "brand": "fastapi",
                "pos": [580, 180],
                "size": [180, 64]
            },
            {
                "id": "auth_service",
                "type": "security",
                "label": "Auth & RBAC Security",
                "sublabel": "JWT (HS256) & Isolation",
                "tag": "Implemented",
                "pos": [840, 180],
                "size": [180, 64]
            },
            {
                "id": "n8n_engine",
                "type": "messagebus",
                "label": "n8n Orchestrator",
                "sublabel": "Multi-Agent Coordinator",
                "tag": "Implemented",
                "pos": [1120, 180],
                "size": [190, 64]
            },
            {
                "id": "doc_pipeline",
                "type": "backend",
                "label": "Document Intake Engine",
                "sublabel": "PDF/DOCX/OCR/SHA-256",
                "tag": "Implemented",
                "pos": [1430, 180],
                "size": [190, 64]
            },

            # -----------------------------------------------------------------
            # ROW 3: STORAGE & ORCHESTRATION DISPATCH (Y=320)
            # -----------------------------------------------------------------
            {
                "id": "db_postgres",
                "type": "database",
                "label": "PostgreSQL Database",
                "sublabel": "Tenders, Bids & Audits",
                "tag": "Implemented",
                "brand": "postgresql",
                "pos": [580, 320],
                "size": [180, 64]
            },
            {
                "id": "storage_vault",
                "type": "database",
                "label": "Private Document Store",
                "sublabel": "Supabase Object Vault",
                "tag": "Implemented",
                "brand": "supabase",
                "pos": [840, 320],
                "size": [180, 64]
            },

            # -----------------------------------------------------------------
            # ROW 4: DETERMINISTIC VERIFICATION SERVICES & ADAPTERS (Y=460)
            # -----------------------------------------------------------------
            {
                "id": "rule_engine",
                "type": "backend",
                "label": "Compliance Rules Engine",
                "sublabel": "Evaluators (Zero LLM)",
                "tag": "Deterministic Core",
                "pos": [580, 490],
                "size": [190, 66]
            },
            {
                "id": "statutory_engine",
                "type": "backend",
                "label": "Statutory ID Verifier",
                "sublabel": "GSTIN / PAN / Udyam",
                "tag": "Deterministic Engine",
                "pos": [890, 450],
                "size": [190, 64]
            },
            {
                "id": "financial_engine",
                "type": "backend",
                "label": "Financial & Exp Verifier",
                "sublabel": "Avg Turnover & Work Orders",
                "tag": "Deterministic Engine",
                "pos": [1140, 450],
                "size": [190, 64]
            },
            {
                "id": "forensics_engine",
                "type": "security",
                "label": "Document Forensics",
                "sublabel": "Similarity & Anomaly",
                "tag": "Deterministic Engine",
                "pos": [890, 580],
                "size": [190, 64]
            },
            {
                "id": "gov_adapters",
                "type": "cloud",
                "label": "Govt Verification Adapters",
                "sublabel": "GST/ITR/MSME/MCA21/EPFO",
                "tag": "Planned Adapters",
                "pos": [1430, 450],
                "size": [190, 66]
            },

            # -----------------------------------------------------------------
            # ROW 5: AI GATEWAY & OPENROUTER (Y=580 & Y=730)
            # -----------------------------------------------------------------
            {
                "id": "ai_gateway",
                "type": "security",
                "label": "Controlled AI Gateway",
                "sublabel": "Ambiguity Guard & Schema",
                "tag": "Implemented",
                "pos": [1140, 580],
                "size": [190, 66]
            },
            {
                "id": "openrouter_api",
                "type": "cloud",
                "label": "OpenRouter API",
                "sublabel": "Target AI Provider",
                "tag": "Planned Integration",
                "pos": [1430, 580],
                "size": [190, 66]
            },

            # -----------------------------------------------------------------
            # ROW 6: EVIDENCE AGGREGATION & FINAL HUMAN DECISION (Y=720)
            # -----------------------------------------------------------------
            {
                "id": "evidence_aggregator",
                "type": "backend",
                "label": "Evidence & Risk Aggregator",
                "sublabel": "Scores, Citations & Hashes",
                "tag": "Implemented",
                "pos": [320, 720],
                "size": [200, 68]
            },
            {
                "id": "officer_final",
                "type": "security",
                "label": "Officer Decision Console",
                "sublabel": "Qualify / Disqualify / Review",
                "tag": "Human Authority",
                "pos": [70, 720],
                "size": [190, 68]
            }
        ],
        "boundaries": [
            {
                "kind": "region",
                "label": "Presentation Layer (React 18 & Vite)",
                "wraps": ["frontend_ui", "frontend_console"],
                "pad": 16
            },
            {
                "kind": "region",
                "label": "Application & Security Layer (FastAPI & RBAC)",
                "wraps": ["fastapi_app", "auth_service"],
                "pad": 16
            },
            {
                "kind": "security-group",
                "label": "Isolated State & Storage Vault",
                "wraps": ["db_postgres", "storage_vault"],
                "pad": 16
            },
            {
                "kind": "region",
                "label": "Deterministic Verification Services (Zero LLM)",
                "wraps": ["rule_engine", "statutory_engine", "financial_engine", "forensics_engine"],
                "pad": 22
            },
            {
                "kind": "security-group",
                "label": "Controlled AI Gateway & Target Provider",
                "wraps": ["ai_gateway", "openrouter_api"],
                "pad": 16
            },
            {
                "kind": "security-group",
                "label": "Evidence Assessment & Statutory Officer Authority",
                "wraps": ["evidence_aggregator", "officer_final"],
                "pad": 18
            }
        ],
        "connections": [
            # 1. Officer straight down to Web UI
            {
                "id": "c_officer_ui",
                "from": "officer",
                "to": "frontend_ui",
                "label": "HTTPS Access",
                "variant": "emphasis"
            },
            # 2. Committee straight down to Console
            {
                "id": "c_committee_console",
                "from": "committee",
                "to": "frontend_console",
                "label": "Audit Review",
                "variant": "default"
            },
            # 3. Web UI to FastAPI
            {
                "id": "c_ui_api",
                "from": "frontend_ui",
                "to": "fastapi_app",
                "label": "REST API",
                "variant": "emphasis",
                "fromSide": "bottom",
                "toSide": "bottom",
                "via": [[160, 260], [670, 260]]
            },
            # 4. Console to FastAPI
            {
                "id": "c_console_api",
                "from": "frontend_console",
                "to": "fastapi_app",
                "label": "Inspection Calls",
                "variant": "default"
            },
            # 5. Auth to FastAPI
            {
                "id": "c_auth_app",
                "from": "auth_service",
                "to": "fastapi_app",
                "label": "JWT & RBAC",
                "variant": "security"
            },
            # 6. GeM Portal to Doc Intake
            {
                "id": "c_gem_intake",
                "from": "gem_portal",
                "to": "doc_pipeline",
                "label": "NIT Intake",
                "variant": "emphasis"
            },
            # 7. FastAPI to Postgres DB
            {
                "id": "c_app_db",
                "from": "fastapi_app",
                "to": "db_postgres",
                "label": "Async SQL",
                "variant": "default"
            },
            # 8. FastAPI to Storage Vault
            {
                "id": "c_app_vault",
                "from": "fastapi_app",
                "to": "storage_vault",
                "label": "Private Vault",
                "variant": "security",
                "fromSide": "bottom",
                "toSide": "left",
                "via": [[670, 352]]
            },
            # 9. FastAPI to n8n Orchestrator
            {
                "id": "c_app_n8n",
                "from": "fastapi_app",
                "to": "n8n_engine",
                "label": "Webhook Trigger",
                "variant": "emphasis",
                "fromSide": "top",
                "toSide": "top",
                "via": [[670, 138], [1215, 138]]
            },
            # 10. n8n to Doc Pipeline
            {
                "id": "c_n8n_doc",
                "from": "n8n_engine",
                "to": "doc_pipeline",
                "label": "Intake Jobs",
                "variant": "default"
            },
            # 11. Doc Pipeline to Verifiers
            {
                "id": "c_doc_stat",
                "from": "doc_pipeline",
                "to": "statutory_engine",
                "label": "Statutory Facts",
                "variant": "default",
                "fromSide": "bottom",
                "toSide": "right",
                "via": [[1525, 390], [1080, 390], [1080, 482]]
            },
            {
                "id": "c_doc_fin",
                "from": "doc_pipeline",
                "to": "financial_engine",
                "label": "Financial Statements",
                "variant": "default",
                "fromSide": "bottom",
                "toSide": "top",
                "via": [[1525, 410], [1235, 410]]
            },
            # 12. Govt Adapters to Statutory Engine (Planned)
            {
                "id": "c_gov_stat",
                "from": "gov_adapters",
                "to": "statutory_engine",
                "label": "External Registry Data",
                "variant": "dashed",
                "fromSide": "top",
                "toSide": "top",
                "via": [[1525, 370], [985, 370]]
            },
            # 13. Verifiers to Rule Engine
            {
                "id": "c_stat_rule",
                "from": "statutory_engine",
                "to": "rule_engine",
                "label": "Verified Identity",
                "variant": "default",
                "fromSide": "left",
                "toSide": "top",
                "via": [[830, 482], [830, 523], [770, 523]]
            },
            {
                "id": "c_forensic_rule",
                "from": "forensics_engine",
                "to": "rule_engine",
                "label": "Forensic Signals",
                "variant": "default",
                "fromSide": "left",
                "toSide": "bottom",
                "via": [[830, 612], [830, 556], [770, 556]]
            },
            {
                "id": "c_fin_rule",
                "from": "financial_engine",
                "to": "rule_engine",
                "label": "Turnover Proof",
                "variant": "default",
                "fromSide": "bottom",
                "toSide": "right",
                "via": [[1235, 523], [770, 523]]
            },
            # 14. Rule Engine to AI Gateway (Escalation only)
            {
                "id": "c_rule_ai",
                "from": "rule_engine",
                "to": "ai_gateway",
                "label": "Ambiguity Escalation",
                "variant": "security",
                "fromSide": "bottom",
                "toSide": "left",
                "via": [[675, 613]]
            },
            # 15. AI Gateway to OpenRouter (Planned)
            {
                "id": "c_ai_openrouter",
                "from": "ai_gateway",
                "to": "openrouter_api",
                "label": "Structured Semantic JSON",
                "variant": "dashed"
            },
            # 16. Rule Engine to Evidence Aggregator
            {
                "id": "c_rule_evidence",
                "from": "rule_engine",
                "to": "evidence_aggregator",
                "label": "Compliance Verification Results",
                "variant": "emphasis",
                "fromSide": "bottom",
                "toSide": "top",
                "via": [[675, 680], [420, 680]]
            },
            # 17. Evidence to Officer Final Review
            {
                "id": "c_evidence_officer",
                "from": "evidence_aggregator",
                "to": "officer_final",
                "label": "Citations & Scores",
                "variant": "emphasis"
            },
            # 18. Officer Final back to Web UI (Upward channel)
            {
                "id": "c_officer_verdict",
                "from": "officer_final",
                "to": "frontend_ui",
                "label": "Officer Decision",
                "variant": "security",
                "fromSide": "top",
                "toSide": "bottom",
                "via": [[160, 680], [160, 244]]
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

if __name__ == "__main__":
    build_architecture()
