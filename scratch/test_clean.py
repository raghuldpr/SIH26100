import json
import subprocess
from pathlib import Path

def test_config():
    # Canvas: 1200 x 675 (16:9)
    # Col 1: X = 40..180 (Width 140)
    # Col 2: X = 270..410 (Width 140)
    # Col 3: X = 500..640 (Width 140)
    # Col 4: X = 730..870 (Width 140)
    # Col 5: X = 960..1110 (Width 150)

    components = [
        # --- Row 1: Users & Portals (Y=40) ---
        {
            "id": "officer",
            "type": "external",
            "label": "Procurement Officer",
            "sublabel": "Tender Authority",
            "tag": "Final Authority",
            "pos": [40, 40],
            "size": [140, 52]
        },
        {
            "id": "committee",
            "type": "external",
            "label": "Tender Committee",
            "sublabel": "Verification Team",
            "tag": "Human Oversight",
            "pos": [270, 40],
            "size": [140, 52]
        },
        {
            "id": "gem_portal",
            "type": "cloud",
            "label": "GeM Portal",
            "sublabel": "Govt e-Marketplace",
            "tag": "Implemented Intake",
            "pos": [960, 40],
            "size": [150, 52]
        },

        # --- Row 2: Presentation & APIs (Y=140) ---
        {
            "id": "frontend_ui",
            "type": "frontend",
            "label": "TenderTrust UI",
            "sublabel": "React 18 + Tailwind",
            "tag": "Implemented",
            "brand": "react",
            "pos": [40, 140],
            "size": [140, 52]
        },
        {
            "id": "frontend_console",
            "type": "frontend",
            "label": "Compliance Console",
            "sublabel": "Evidence & Audit",
            "tag": "Implemented",
            "pos": [270, 140],
            "size": [140, 52]
        },
        {
            "id": "fastapi_app",
            "type": "backend",
            "label": "FastAPI Core",
            "sublabel": "REST API Engine",
            "tag": "Implemented",
            "brand": "fastapi",
            "pos": [500, 140],
            "size": [140, 52]
        },
        {
            "id": "auth_service",
            "type": "security",
            "label": "Auth & RBAC",
            "sublabel": "JWT & Isolation",
            "tag": "Implemented",
            "pos": [730, 140],
            "size": [140, 52]
        },
        {
            "id": "doc_pipeline",
            "type": "backend",
            "label": "Document Intake",
            "sublabel": "PDF/OCR/SHA-256",
            "tag": "Implemented",
            "pos": [960, 140],
            "size": [150, 52]
        },

        # --- Row 3: Data Storage & Orchestration (Y=245) ---
        {
            "id": "db_postgres",
            "type": "database",
            "label": "PostgreSQL DB",
            "sublabel": "Bids & Audit State",
            "tag": "Implemented",
            "brand": "postgresql",
            "pos": [500, 245],
            "size": [140, 52]
        },
        {
            "id": "storage_vault",
            "type": "database",
            "label": "Document Vault",
            "sublabel": "Supabase Storage",
            "tag": "Implemented",
            "brand": "supabase",
            "pos": [730, 245],
            "size": [140, 52]
        },
        {
            "id": "n8n_engine",
            "type": "messagebus",
            "label": "n8n Orchestrator",
            "sublabel": "Multi-Agent Hub",
            "tag": "Implemented",
            "pos": [960, 245],
            "size": [150, 52]
        },

        # --- Row 4: Deterministic Verifiers (Y=350) ---
        {
            "id": "rule_engine",
            "type": "backend",
            "label": "Rule Engine",
            "sublabel": "Deterministic (No LLM)",
            "tag": "Core Evaluator",
            "pos": [500, 350],
            "size": [140, 52]
        },
        {
            "id": "statutory_engine",
            "type": "backend",
            "label": "Statutory Verifier",
            "sublabel": "GST / PAN / Udyam",
            "tag": "Deterministic",
            "pos": [730, 350],
            "size": [140, 52]
        },
        {
            "id": "financial_engine",
            "type": "backend",
            "label": "Financial Verifier",
            "sublabel": "Turnover (Sum÷N)",
            "tag": "Deterministic",
            "pos": [960, 350],
            "size": [150, 52]
        },

        # --- Row 5: AI Gateway & Target Provider (Y=455) ---
        {
            "id": "ai_gateway",
            "type": "security",
            "label": "AI Gateway",
            "sublabel": "Guardrails & Schema",
            "tag": "Controlled",
            "pos": [500, 455],
            "size": [140, 52]
        },
        {
            "id": "openrouter_api",
            "type": "cloud",
            "label": "OpenRouter API",
            "sublabel": "Target AI Provider",
            "tag": "Planned Integration",
            "pos": [730, 455],
            "size": [140, 52]
        },
        {
            "id": "gov_adapters",
            "type": "cloud",
            "label": "Govt Adapters",
            "sublabel": "GST/ITR/MSME/MCA",
            "tag": "Planned Adapters",
            "pos": [960, 455],
            "size": [150, 52]
        },

        # --- Row 6: Evidence & Final Review (Y=560) ---
        {
            "id": "officer_final",
            "type": "security",
            "label": "Officer Final Review",
            "sublabel": "Qualify / Disqualify",
            "tag": "Human Decision",
            "pos": [40, 560],
            "size": [140, 54]
        },
        {
            "id": "evidence_aggregator",
            "type": "backend",
            "label": "Evidence Aggregator",
            "sublabel": "Citations & Scores",
            "tag": "Implemented",
            "pos": [270, 560],
            "size": [140, 54]
        }
    ]

    boundaries = [
        {
            "kind": "region",
            "label": "Presentation Layer (React 18 & Vite)",
            "wraps": ["frontend_ui", "frontend_console"],
            "pad": 14
        },
        {
            "kind": "region",
            "label": "Application Layer (FastAPI Backend)",
            "wraps": ["fastapi_app", "auth_service"],
            "pad": 14
        },
        {
            "kind": "security-group",
            "label": "Isolated State Vault",
            "wraps": ["db_postgres", "storage_vault"],
            "pad": 14
        },
        {
            "kind": "region",
            "label": "Deterministic Verification Services (Zero LLM)",
            "wraps": ["rule_engine", "statutory_engine", "financial_engine"],
            "pad": 18
        },
        {
            "kind": "security-group",
            "label": "Controlled AI Gateway (OpenRouter)",
            "wraps": ["ai_gateway", "openrouter_api"],
            "pad": 14
        },
        {
            "kind": "security-group",
            "label": "Evidence Assessment & Officer Authority",
            "wraps": ["evidence_aggregator", "officer_final"],
            "pad": 16
        }
    ]

    connections = [
        # 1. Officer -> UI (straight down)
        {
            "id": "c_officer_ui",
            "from": "officer",
            "to": "frontend_ui",
            "label": "HTTPS",
            "variant": "emphasis",
            "labelAt": [110, 115]
        },
        # 2. Committee -> Console (straight down)
        {
            "id": "c_committee_console",
            "from": "committee",
            "to": "frontend_console",
            "label": "Audit UI",
            "variant": "default",
            "labelAt": [340, 115]
        },
        # 3. UI -> Console (direct horizontal)
        {
            "id": "c_ui_console",
            "from": "frontend_ui",
            "to": "frontend_console",
            "label": "Views",
            "variant": "default"
        },
        # 4. Console -> FastAPI (direct horizontal)
        {
            "id": "c_console_api",
            "from": "frontend_console",
            "to": "fastapi_app",
            "label": "REST API",
            "variant": "emphasis"
        },
        # 5. Auth -> FastAPI (direct horizontal)
        {
            "id": "c_auth_app",
            "from": "auth_service",
            "to": "fastapi_app",
            "label": "RBAC",
            "variant": "security"
        },
        # 6. GeM Portal -> Doc Intake (straight down)
        {
            "id": "c_gem_intake",
            "from": "gem_portal",
            "to": "doc_pipeline",
            "label": "NIT Intake",
            "variant": "emphasis",
            "labelAt": [1035, 115]
        },
        # 7. FastAPI -> Postgres (straight down)
        {
            "id": "c_app_db",
            "from": "fastapi_app",
            "to": "db_postgres",
            "label": "Async SQL",
            "variant": "default",
            "labelAt": [570, 218]
        },
        # 8. Auth -> Storage (straight down)
        {
            "id": "c_auth_vault",
            "from": "auth_service",
            "to": "storage_vault",
            "label": "Storage Policy",
            "variant": "security",
            "labelAt": [800, 218]
        },
        # 9. Doc Pipeline -> n8n (straight down)
        {
            "id": "c_doc_n8n",
            "from": "doc_pipeline",
            "to": "n8n_engine",
            "label": "Intake Artifacts",
            "variant": "default",
            "labelAt": [1035, 218]
        },
        # 10. n8n -> Financial Engine (straight down)
        {
            "id": "c_n8n_fin",
            "from": "n8n_engine",
            "to": "financial_engine",
            "label": "Dispatch",
            "variant": "default",
            "labelAt": [1035, 323]
        },
        # 11. Financial -> Statutory (direct horizontal)
        {
            "id": "c_fin_stat",
            "from": "financial_engine",
            "to": "statutory_engine",
            "label": "Turnover Proof",
            "variant": "default"
        },
        # 12. Statutory -> Rule Engine (direct horizontal)
        {
            "id": "c_stat_rule",
            "from": "statutory_engine",
            "to": "rule_engine",
            "label": "Verified Facts",
            "variant": "default"
        },
        # 13. Govt Adapters -> Financial Engine (straight up)
        {
            "id": "c_gov_fin",
            "from": "gov_adapters",
            "to": "financial_engine",
            "label": "Govt Registries",
            "variant": "dashed",
            "labelAt": [1035, 428]
        },
        # 14. Rule Engine -> AI Gateway (straight down)
        {
            "id": "c_rule_ai",
            "from": "rule_engine",
            "to": "ai_gateway",
            "label": "Ambiguity Escalation",
            "variant": "security",
            "labelAt": [570, 428]
        },
        # 15. AI Gateway -> OpenRouter (direct horizontal)
        {
            "id": "c_ai_openrouter",
            "from": "ai_gateway",
            "to": "openrouter_api",
            "label": "Semantic JSON",
            "variant": "dashed"
        },
        # 16. Rule Engine -> Evidence Aggregator (via left corridor)
        {
            "id": "c_rule_evidence",
            "from": "rule_engine",
            "to": "evidence_aggregator",
            "label": "Compliance Score",
            "variant": "emphasis",
            "fromSide": "left",
            "toSide": "top",
            "via": [[440, 376], [340, 376], [340, 560]]
        },
        # 17. Evidence -> Officer Final (direct horizontal)
        {
            "id": "c_evidence_officer",
            "from": "evidence_aggregator",
            "to": "officer_final",
            "label": "Audit Trail",
            "variant": "emphasis"
        },
        # 18. Officer Final -> UI (straight up)
        {
            "id": "c_officer_verdict",
            "from": "officer_final",
            "to": "frontend_ui",
            "label": "Final Decision",
            "variant": "security",
            "fromSide": "top",
            "toSide": "bottom",
            "labelAt": [110, 375]
        }
    ]

    cards = [
        {
            "dot": "emerald",
            "title": "Deterministic-First Verification",
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

    arch = {
        "schema_version": 1,
        "diagram_type": "architecture",
        "meta": {
            "title": "TenderTrust — Reliable Procurement Decisions Architecture",
            "subtitle": "AI-Assisted GeM Bid Compliance Verification Platform with Deterministic-First Engine & Human Governance",
            "output": "tendertrust_architecture.html",
            "quality_profile": "showcase",
            "viewBox": [1200, 675],
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
                        "rule_engine", "evidence_aggregator"
                    ],
                    "note": "Strict rule-based verification: statutory identity, financial arithmetic (Sum÷N), and zero-LLM compliance."
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
        "components": components,
        "boundaries": boundaries,
        "connections": connections,
        "cards": cards
    }

    out_path = Path("tendertrust_architecture.architecture.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(arch, f, indent=2)

    print(f"Written {out_path}")

test_config()
