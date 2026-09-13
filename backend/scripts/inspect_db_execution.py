import json
from app.core.database import SessionLocal
from app.models.verification import VerificationExecution
from app.models.tender_requirement import TenderRequirement
from app.models.document import Document
from app.models.compliance import BidderEvidenceModel

db = SessionLocal()
print("=== DOCUMENTS ===")
docs = db.query(Document).all()
for d in docs:
    print(f"\nDoc: id={d.id}, name={d.original_filename}, type={d.document_type}, status={d.processing_status}")
    if d.extracted_data:
        print(f"  Extracted data keys: {list(d.extracted_data.keys())}")
        if "text" in d.extracted_data:
            text = d.extracted_data["text"][:300].replace('\n', ' ')
            print(f"  Text snippet: {text}...")
        for k in ["entities", "tables", "financial_data", "experience_data"]:
            if k in d.extracted_data:
                print(f"  {k}: {json.dumps(d.extracted_data[k], indent=2)}")

print("\n=== BIDDER EVIDENCE ROWS ===")
evs = db.query(BidderEvidenceModel).all()
for ev in evs:
    print(f"Evidence: field={ev.field}, value={ev.value}, conf={ev.confidence}, doc_id={ev.document_id}")

db.close()
