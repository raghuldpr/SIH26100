import os
import sys
from pathlib import Path
from dotenv import load_dotenv

root_dir = Path(__file__).resolve().parent.parent
load_dotenv(root_dir / ".env")
sys.path.insert(0, str(root_dir / "backend"))

from app.core.database import SessionLocal
from sqlalchemy import text

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

def main():
    with SessionLocal() as session:
        counts_before = {t: session.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar() for t in TABLES}
        print(f"Row counts before cleanup: {counts_before}")
        
        if any(c > 0 for c in counts_before.values()):
            print("Cleaning up rows...")
            for t in TABLES:
                session.execute(text(f"DELETE FROM {t}"))
            session.commit()
            
        counts_after = {t: session.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar() for t in TABLES}
        print(f"Row counts after cleanup: {counts_after}")
        for t, c in counts_after.items():
            assert c == 0, f"Table {t} still has {c} rows!"
        print("ALL 11 TABLES CONFIRMED AT 0 ROWS.")

if __name__ == "__main__":
    main()
