"""
SIH-26100 Phase 19: End-to-End Production API + Frontend Integration Test
Verifies all 14 workflow steps against live FastAPI application and cleans up all data.
"""
import os
import sys
import uuid
import json
from pathlib import Path
from dotenv import load_dotenv

root_dir = Path(__file__).resolve().parent.parent
# Load .env from root
load_dotenv(root_dir / ".env")

# Set python path to backend
backend_dir = root_dir / "backend"
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from sqlalchemy import text
from app.services.storage_service import storage_service

TABLES = [
    "verification_audit_events",
    "verification_executions",
    "compliance_results",
    "bidder_evidence",
    "requirements",
    "tender_requirements",
    "documents",
    "tender_bidders",
    "bidders",
    "tenders",
    "users",
]

def check_table_counts(session):
    counts = {}
    for table in TABLES:
        res = session.execute(text(f"SELECT COUNT(*) FROM {table}"))
        counts[table] = res.scalar()
    return counts

def cleanup_all(session):
    for table in TABLES:
        session.execute(text(f"DELETE FROM {table}"))
    session.commit()

def main():
    print("=== SIH-26100 PHASE 19: E2E WORKFLOW INTEGRATION VERIFICATION ===")
    
    # 0. Check initial database state
    with SessionLocal() as session:
        init_counts = check_table_counts(session)
        print(f"Initial DB row counts: {init_counts}")
        if any(c > 0 for c in init_counts.values()):
            print("Cleaning prior residues before test...")
            cleanup_all(session)
    
    uploaded_storage_paths = []
    
    with TestClient(app, base_url="http://testserver") as client:
        # 1. User Registration & Login -> JWT Token
        test_email = f"officer_{uuid.uuid4().hex[:6]}@sih26100.gov.in"
        test_pwd = "StrongSecurePassword123!"
        
        print("\nStep 1: User Registration & Login")
        reg_res = client.post("/api/v1/auth/register", json={
            "email": test_email,
            "password": test_pwd,
            "name": "Senior Procurement Officer",
            "role": "ADMIN"
        })
        assert reg_res.status_code in (200, 201), f"Registration failed: {reg_res.text}"
        reg_data = reg_res.json()
        print(f"  User registered: {reg_data.get('email')} (ID: {reg_data.get('id')})")
        
        login_res = client.post("/api/v1/auth/login", json={
            "email": test_email,
            "password": test_pwd
        })
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        login_data = login_res.json()
        token = login_data.get("token", {}).get("access_token") or login_data.get("access_token")
        assert token, f"JWT token missing from login response: {login_data}"
        headers = {"Authorization": f"Bearer {token}"}
        print("  Login successful. JWT token received.")
        
        # 2. Dashboard View
        print("\nStep 2: Dashboard View")
        me_res = client.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200, f"/auth/me failed: {me_res.text}"
        
        tenders_list_res = client.get("/api/v1/tenders", headers=headers)
        assert tenders_list_res.status_code == 200
        
        bidders_list_res = client.get("/api/v1/bidders", headers=headers)
        assert bidders_list_res.status_code == 200
        
        docs_list_res = client.get("/api/v1/documents", headers=headers)
        assert docs_list_res.status_code == 200
        
        verifs_list_res = client.get("/api/v1/verification/history", headers=headers)
        assert verifs_list_res.status_code == 200
        print("  Dashboard endpoints verified.")
        
        # 3. Tender Creation
        print("\nStep 3: Tender Creation")
        tender_num = f"TND-{uuid.uuid4().hex[:8].upper()}"
        create_tnd_res = client.post("/api/v1/tenders", headers=headers, json={
            "tender_number": tender_num,
            "title": "Supply and Maintenance of High-Capacity Enterprise Networking Hardware",
            "description": "Comprehensive procurement requiring ISO certification, financial minimums, and strict statutory compliance.",
            "organization": "National Informatics Centre",
            "department": "Infrastructure & Cloud Services",
            "status": "OPEN",
            "estimated_value": 45000000.0,
            "category": "HARDWARE"
        })
        assert create_tnd_res.status_code in (200, 201), f"Tender creation failed: {create_tnd_res.text}"
        tender = create_tnd_res.json()
        tender_id = tender["id"]
        print(f"  Tender created: {tender['tender_number']} (ID: {tender_id})")
        
        # 4. Document Upload (Tender document to Supabase Storage via backend)
        print("\nStep 4: Tender Document Upload")
        import fitz
        tnd_fitz = fitz.open()
        tnd_page = tnd_fitz.new_page()
        tnd_page.insert_text((50, 72), """NOTICE INVITING TENDER
Ref: """ + tender_num + """
SECTION III: QUALIFICATION & ELIGIBILITY CRITERIA
1. The bidder must have valid GST registration certificate and provide active GSTIN.
2. The bidder must have an average annual turnover of at least Rs. 10 Lakhs during the last three financial years.
3. The bidder must have at least 5 years of experience in similar contracts.
4. The bidder must have past experience and track record with sufficient experience in cloud systems.
""")
        dummy_nit_content = tnd_fitz.tobytes()
        tnd_fitz.close()

        files = {
            "file": ("NIT_Technical_Specifications.pdf", dummy_nit_content, "application/pdf")
        }
        data = {
            "document_type": "TENDER_NOTICE"
        }
        upload_tnd_doc_res = client.post(f"/api/v1/tenders/{tender_id}/documents", headers=headers, files=files, data=data)
        assert upload_tnd_doc_res.status_code in (200, 201), f"Tender doc upload failed: {upload_tnd_doc_res.text}"
        tnd_doc = upload_tnd_doc_res.json()
        tnd_doc_path = tnd_doc.get("storage_path")
        if tnd_doc_path:
            uploaded_storage_paths.append(tnd_doc_path)
        print(f"  Tender document uploaded: {tnd_doc['original_filename']} (Storage Path: {tnd_doc_path})")
        
        # 5. Tender Intelligence: Extract compliance requirements
        print("\nStep 5: Tender Intelligence Analysis")
        analyze_res = client.post(f"/api/v1/tenders/{tender_id}/intelligence/analyze", headers=headers, json={
            "force_reanalyze": True
        })
        assert analyze_res.status_code == 200, f"Intelligence analyze failed: {analyze_res.text}"
        profile = analyze_res.json()
        req_count = profile.get("requirement_count", 0)
        det_count = profile.get("deterministic_count", 0)
        ai_count = profile.get("ai_escalations", 0)
        print(f"  Intelligence extracted {req_count} requirements ({det_count} deterministic, {ai_count} AI-assisted)")
        
        # 6. Requirements Review
        print("\nStep 6: Requirements Review")
        reqs_res = client.get(f"/api/v1/tenders/{tender_id}/requirements", headers=headers)
        assert reqs_res.status_code == 200, f"Get requirements failed: {reqs_res.text}"
        reqs = reqs_res.json()
        req_items = reqs if isinstance(reqs, list) else reqs.get("items", reqs.get("data", []))
        print(f"  Retrieved {len(req_items)} requirements.")
        for r in req_items[:4]:
            print(f"    - [{r.get('resolution_method', 'DETERMINISTIC')}] Rule: {r.get('rule')}, Conf: {r.get('confidence')}")
        
        # 7. Bidder Registration
        print("\nStep 7: Bidder Registration")
        gst_num = "27AABCU9603R1ZM"
        pan_num = "AABCU9603R"
        create_bidder_res = client.post("/api/v1/bidders", headers=headers, json={
            "company_name": "Apex Global Solutions Private Limited",
            "gst_number": gst_num,
            "pan_number": pan_num,
            "udyam_number": "UDYAM-MH-01-0012345",
            "contact_person": "Vikram Malhotra",
            "email": "contact@apexsolutions.in",
            "phone": "+919876543210",
            "status": "ACTIVE"
        })
        assert create_bidder_res.status_code in (200, 201), f"Bidder registration failed: {create_bidder_res.text}"
        bidder = create_bidder_res.json()
        bidder_id = bidder["id"]
        print(f"  Bidder registered: {bidder['company_name']} (GSTIN: {bidder['gst_number']}, ID: {bidder_id})")
        
        # 8. Bidder Assignment
        print("\nStep 8: Bidder Assignment to Tender")
        assign_res = client.post(f"/api/v1/tenders/{tender_id}/bidders/{bidder_id}", headers=headers)
        assert assign_res.status_code in (200, 201), f"Assign bidder failed: {assign_res.text}"
        assign_data = assign_res.json()
        print(f"  Bidder assigned to tender: {assign_data.get('company_name', 'Enrolled')}")
        
        # Verify assignment via GET /tenders/{id}/bidders
        tnd_bidders_res = client.get(f"/api/v1/tenders/{tender_id}/bidders", headers=headers)
        assert tnd_bidders_res.status_code == 200
        assigned_list = tnd_bidders_res.json()
        assert len(assigned_list) >= 1, "Assigned bidder not listed in tender bidders"
        print(f"  Confirmed bidder enrolled in tender bidders list.")
        
        # 9. Bidder Document Upload
        print("\nStep 9: Bidder Document Upload")
        bdr_fitz = fitz.open()
        bdr_page = bdr_fitz.new_page()
        bdr_page.insert_text((50, 72), """GST REGISTRATION CERTIFICATE & FINANCIAL STATEMENT
Government of India
GSTIN: 27AABCU9603R1ZM
Legal Name: Apex Global Solutions Private Limited
PAN: AABCU9603R
Audited Annual Turnover: Rs. 35,00,000 (Thirty Five Lakhs)
Experience: 6 years in cloud systems and enterprise infrastructure.
""")
        dummy_bidder_doc = bdr_fitz.tobytes()
        bdr_fitz.close()

        files = {
            "file": ("GST_Registration_Certificate.pdf", dummy_bidder_doc, "application/pdf")
        }
        data = {
            "document_type": "GST",
            "tender_id": tender_id
        }
        upload_bdr_doc_res = client.post(f"/api/v1/bidders/{bidder_id}/documents", headers=headers, files=files, data=data)
        assert upload_bdr_doc_res.status_code in (200, 201), f"Bidder doc upload failed: {upload_bdr_doc_res.text}"
        bdr_doc = upload_bdr_doc_res.json()
        bdr_doc_path = bdr_doc.get("storage_path")
        if bdr_doc_path:
            uploaded_storage_paths.append(bdr_doc_path)
        print(f"  Bidder evidence uploaded: {bdr_doc['original_filename']} (Storage Path: {bdr_doc_path})")
        
        # 10. Verification Execution (trigger verification against tender requirements)
        print("\nStep 10: Verification Execution")
        verif_run_res = client.post("/api/v1/verification/run", headers=headers, json={
            "tender_id": tender_id,
            "bidder_id": bidder_id
        })
        assert verif_run_res.status_code == 200, f"Verification run failed: {verif_run_res.text}"
        verif = verif_run_res.json()
        verification_id = verif["verification_id"]
        print(f"  Verification executed successfully. ID: {verification_id}")
        
        # 11. Compliance Breakdown
        print("\nStep 11: Compliance Breakdown")
        requirements_eval = verif.get("requirements", [])
        print(f"  Evaluated {len(requirements_eval)} clauses:")
        for r in requirements_eval[:4]:
            print(f"    - {r.get('rule')}: Decision={r.get('decision')} | Conf={r.get('confidence')}")
        
        # 12. Verification Outcome
        print("\nStep 12: Verification Outcome")
        print(f"  Decision: {verif.get('decision')}")
        print(f"  Risk Level: {verif.get('risk_level')} (Risk Score: {verif.get('risk_score')})")
        print(f"  Canonical Result Hash: {verif.get('result_hash')}")
        assert verif.get("result_hash"), "Result hash must be computed and present"
        assert verif.get("decision"), "Decision must be present"
        
        # 13. Verification History
        print("\nStep 13: Verification History")
        hist_res = client.get(f"/api/v1/verification/tender/{tender_id}/bidder/{bidder_id}", headers=headers)
        assert hist_res.status_code == 200, f"Pair history failed: {hist_res.text}"
        hist_items = hist_res.json()
        assert len(hist_items) >= 1, "History item not recorded for tender & bidder pair"
        print(f"  Tender-Bidder pair history recorded: {len(hist_items)} runs.")
        
        global_hist_res = client.get("/api/v1/verification/history", headers=headers)
        assert global_hist_res.status_code == 200, f"Global history failed: {global_hist_res.text}"
        global_hist = global_hist_res.json()
        assert len(global_hist) >= 1, "Global history item missing"
        print(f"  Global verification history contains: {len(global_hist)} executions.")
        
        # 14. Audit Trail
        print("\nStep 14: Audit Trail")
        audit_res = client.get(f"/api/v1/verification/{verification_id}/audit", headers=headers)
        assert audit_res.status_code == 200, f"Audit trail failed: {audit_res.text}"
        audit_events = audit_res.json()
        assert len(audit_events) >= 1, "Audit events not logged"
        print(f"  Audit trail verified with {len(audit_events)} lifecycle events:")
        for ev in audit_events:
            print(f"    - [{ev.get('created_at')}] Event: {ev.get('event_type')}")
        
        # Storage download check
        print("\nPresigned Download URL Check:")
        docs_res = client.get("/api/v1/documents", headers=headers)
        assert docs_res.status_code == 200
        docs_data = docs_res.json()
        items = docs_data.get("items", [])
        assert len(items) >= 2, "Both tender and bidder docs should be listed"
        for doc_item in items:
            assert doc_item.get("download_url"), f"Document {doc_item['id']} missing download_url"
        print(f"  Verified {len(items)} documents with active presigned download URLs.")

    # 15. Cleanup synthetic test data from database and Supabase storage
    print("\nStep 15: Cleaning up synthetic test data...")
    # Delete uploaded storage files
    try:
        for s_path in uploaded_storage_paths:
            storage_service.delete(s_path)
            print(f"  Storage object deleted: {s_path}")
    except Exception as e:
        print(f"  Storage deletion notice: {e}")

    with SessionLocal() as session:
        cleanup_all(session)
        final_counts = check_table_counts(session)
        print(f"\nFinal DB row counts: {final_counts}")
        for t, c in final_counts.items():
            assert c == 0, f"Table {t} has non-zero rows: {c}"
    
    print("\nSUCCESS: All 14 workflow steps passed and database cleanly restored to 0 rows in all 11 tables!")

if __name__ == "__main__":
    main()
