"""
API Tests for FastAPI ↔ n8n Verification Endpoints
tests/test_verification_api.py
"""
import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.models.bidder import Bidder
from app.models.tender import Tender
from app.schemas.verification import (
    N8nAgentResult,
    N8nVerificationResponse,
    RiskLevelEnum,
    VerificationDecisionEnum,
    VerificationResponse,
    VerificationStatusEnum,
)
from app.services.n8n_client import n8n_client

client = TestClient(app)


@pytest.fixture
def mock_tender_id():
    return uuid.uuid4()


@pytest.fixture
def mock_bidder_id():
    return uuid.uuid4()


@pytest.fixture
def sample_trigger_payload(mock_tender_id, mock_bidder_id):
    return {
        "tender_id": str(mock_tender_id),
        "bidder_id": str(mock_bidder_id),
        "required_agents": ["GST_AGENT", "PAN_AGENT", "FINANCIAL_AGENT"],
        "financial_overrides": {
            "average_turnover": 10000000.0,
            "minimum_net_worth": 5000000.0,
        },
    }


@pytest.fixture
def mock_n8n_resp(mock_tender_id, mock_bidder_id):
    return N8nVerificationResponse(
        verification_id="VER-TEST-12345",
        request_id="REQ-TEST-12345",
        tender_id=str(mock_tender_id),
        bidder_id=str(mock_bidder_id),
        bidder_name="Alpha Tech Infra",
        status="COMPLETED",
        decision="QUALIFIED",
        risk_score=15.0,
        risk_level="LOW",
        agent_results=[
            N8nAgentResult(
                agent="GST_AGENT",
                status="VERIFIED",
                confidence=0.95,
                evidence={"active": True},
                issues=[],
                risk_level="LOW",
            )
        ],
        reasons=["All criteria passed"],
    )


class TestVerificationApiEndpoints:
    """Tests for /api/v1/verification router."""

    def test_health_endpoint(self):
        with patch.object(n8n_client, "check_health", new_callable=AsyncMock) as mock_health:
            mock_health.return_value = {
                "reachable": True,
                "status_code": 200,
                "base_url": "http://localhost:5678",
            }
            response = client.get("/api/v1/verification/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["n8n_service"]["reachable"] is True

    def test_trigger_verification_success(self, sample_trigger_payload, mock_tender_id, mock_bidder_id, mock_n8n_resp):
        # Mock DB querying and verification service execution
        with patch("app.api.v1.endpoints.verification.verification_service.execute_verification", new_callable=AsyncMock) as mock_exec, \
             patch("sqlalchemy.orm.Session.query") as mock_query:
            
            # Setup mock DB records for Tender and Bidder
            mock_tender = Tender(id=mock_tender_id, title="Test Tender")
            mock_bidder = Bidder(id=mock_bidder_id, company_name="Alpha Tech Infra")

            mock_q = mock_query.return_value
            mock_q.filter.return_value.first.side_effect = [mock_tender, mock_bidder]

            mock_exec.return_value = VerificationResponse(
                id=uuid.uuid4(),
                verification_id=mock_n8n_resp.verification_id,
                request_id=mock_n8n_resp.request_id,
                tender_id=mock_tender_id,
                bidder_id=mock_bidder_id,
                bidder_name="Alpha Tech Infra",
                status=VerificationStatusEnum.COMPLETED,
                decision=VerificationDecisionEnum.QUALIFIED,
                risk_score=15.0,
                risk_level=RiskLevelEnum.LOW,
                reasons=["All criteria passed"],
                failed_requirements=[],
                warnings=[],
                missing_documents=[],
                agent_results=mock_n8n_resp.agent_results,
            )

            response = client.post("/api/v1/verification/trigger", json=sample_trigger_payload)
            assert response.status_code == 200
            data = response.json()
            assert data["verification_id"] == "VER-TEST-12345"
            assert data["decision"] == "QUALIFIED"
            assert data["risk_score"] == 15.0

    def test_webhook_callback_valid_signature(self, mock_tender_id, mock_bidder_id):
        callback_payload = {
            "verification_id": "VER-CB-999",
            "request_id": "REQ-CB-999",
            "tender_id": str(mock_tender_id),
            "bidder_id": str(mock_bidder_id),
            "bidder_name": "Apex Builders",
            "status": "COMPLETED",
            "decision": "QUALIFIED",
            "risk_score": 10.0,
            "risk_level": "LOW",
            "agent_results": [],
            "reasons": ["Verified via callback"],
        }
        body_bytes = json.dumps(callback_payload).encode("utf-8")
        signature = n8n_client.generate_signature(body_bytes)

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Secret": settings.N8N_WEBHOOK_SECRET,
            "X-Webhook-Signature": f"sha256={signature}",
        }

        response = client.post("/api/v1/verification/webhook/callback", content=body_bytes, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"
        assert data["verification_id"] == "VER-CB-999"

    def test_webhook_callback_invalid_secret(self):
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Secret": "wrong-secret",
        }
        response = client.post("/api/v1/verification/webhook/callback", json={"test": 123}, headers=headers)
        assert response.status_code == 401

    def test_webhook_callback_invalid_signature(self):
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Secret": settings.N8N_WEBHOOK_SECRET,
            "X-Webhook-Signature": "sha256=invalid-signature",
        }
        response = client.post("/api/v1/verification/webhook/callback", json={"test": 123}, headers=headers)
        assert response.status_code == 401
