"""
Phase 12.9 — Live n8n E2E Smoke Test
"""
import asyncio
import json
import sys
import uuid
import httpx

from app.db.session import SessionLocal
from app.schemas.verification import VerificationTriggerRequest
from app.services.n8n_client import n8n_client
from app.services.verification_service import verification_service
from tests.test_phase12_live_e2e_phase12_9 import TestPhase12LiveE2EPhase129


def run_smoke_test():
    print("=" * 70)
    print("           PHASE 12.9 FINAL LIVE N8N E2E SMOKE TEST")
    print("=" * 70)

    test_harness = TestPhase12LiveE2EPhase129()
    test_harness.setUp()
    try:
        tender = test_harness._create_synthetic_tender()
        bidder = test_harness._create_synthetic_bidder(tender.id)

        loop = asyncio.new_event_loop()

        # Step 1: Health
        health = loop.run_until_complete(n8n_client.check_health())
        print(f"1. n8n Health Status: HTTP {health.get('status_code')} (Reachable: {health.get('reachable')})")
        assert health.get("reachable") is True, "n8n is not reachable"

        # Step 2: Verification Trigger & Execution
        req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id)
        res = loop.run_until_complete(verification_service.execute_verification(trigger_request=req, db=test_harness.db))

        print(f"2. Verification ID: {res.verification_id}")
        print(f"   Tender ID: {res.tender_id}")
        print(f"   Bidder ID: {res.bidder_id} ({res.bidder_name})")
        print(f"   Status: {res.status.value}")
        print(f"   Decision: {res.decision.value}")
        print(f"   Overall Compliance: {res.overall_compliance.value}")
        print(f"   Risk Level: {res.risk_level.value} (Score: {res.risk_score})")
        print(f"   Deterministic Result Hash: {res.result_hash}")
        print(f"   Agents Executed: {len(res.agent_results)}")
        for agent_res in res.agent_results:
            print(f"     - {agent_res.agent}: {agent_res.status} (Risk: {agent_res.risk_level}, Confidence: {agent_res.confidence})")

        print("=" * 70)
        print("LIVE_N8N_SMOKE_TEST = PASS")
        print("=" * 70)
    finally:
        test_harness.tearDown()


if __name__ == "__main__":
    run_smoke_test()
