"""
Unit & Integration Tests for n8n Client Service
tests/test_n8n_client.py
"""
import json
import pytest
import httpx

from app.schemas.verification import (
    N8nAgentResult,
    N8nVerificationPayload,
    N8nVerificationResponse,
)
from app.services.n8n_client import (
    N8nClient,
    N8nClientError,
    N8nConnectionError,
    N8nTimeoutError,
)


@pytest.fixture
def sample_n8n_payload() -> N8nVerificationPayload:
    return N8nVerificationPayload(
        request_id="REQ-TEST-001",
        verification_id="VER-TEST-001",
        tender_id="TENDER-001",
        bidder_id="BIDDER-001",
        bidder_name="Apex Infra Solutions Pvt Ltd",
        gstin="29ABCDE1234F1Z5",
        pan="ABCDE1234F",
    )


@pytest.fixture
def sample_n8n_success_json() -> dict:
    return {
        "verification_id": "VER-TEST-001",
        "request_id": "REQ-TEST-001",
        "tender_id": "TENDER-001",
        "bidder_id": "BIDDER-001",
        "bidder_name": "Apex Infra Solutions Pvt Ltd",
        "status": "COMPLETED",
        "decision": "QUALIFIED",
        "risk_score": 12.5,
        "risk_level": "LOW",
        "agent_results": [
            {
                "agent": "GST_AGENT",
                "status": "VERIFIED",
                "confidence": 0.98,
                "evidence": {"gstin_active": True},
                "issues": [],
                "risk_level": "LOW",
            },
            {
                "agent": "PAN_AGENT",
                "status": "VERIFIED",
                "confidence": 0.99,
                "evidence": {"pan_valid": True},
                "issues": [],
                "risk_level": "LOW",
            },
        ],
        "failed_requirements": [],
        "missing_documents": [],
        "warnings": [],
        "reasons": ["All statutory and financial criteria satisfied."],
    }


class TestN8nClientSecurity:
    """Tests for HMAC signature generation, headers, and secret verification."""

    def test_generate_and_verify_signature(self):
        client = N8nClient(webhook_secret="test-secret-key-123")
        payload = b'{"request_id": "REQ-001", "bidder": "ABC"}'

        sig = client.generate_signature(payload)
        assert isinstance(sig, str)
        assert len(sig) == 64  # SHA256 hex string

        # Exact match verification
        assert client.verify_webhook_signature(payload, sig) is True
        assert client.verify_webhook_signature(payload, f"sha256={sig}") is True

        # Tampered payload fails
        assert client.verify_webhook_signature(b'{"tampered": true}', sig) is False
        assert client.verify_webhook_signature(payload, "invalid-sig") is False

    def test_auth_headers_construction(self):
        client = N8nClient(
            api_key="my-api-key",
            webhook_secret="my-webhook-secret",
        )
        body = b'{"test": 123}'
        headers = client.get_auth_headers(body=body)

        assert headers["Content-Type"] == "application/json"
        assert headers["Authorization"] == "Bearer my-api-key"
        assert headers["X-N8N-API-KEY"] == "my-api-key"
        assert headers["X-Webhook-Secret"] == "my-webhook-secret"
        assert "X-Webhook-Signature" in headers
        assert headers["X-Webhook-Signature"].startswith("sha256=")


@pytest.mark.asyncio
class TestN8nClientDispatch:
    """Tests for HTTP dispatching, responses, retries, and error handling."""

    async def test_successful_verification_dispatch(self, sample_n8n_payload, sample_n8n_success_json):
        # Mock transport returning 200 OK
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url == "http://mock-n8n:5678/webhook/bid-verification"
            data = json.loads(request.read())
            assert data["bidder_name"] == "Apex Infra Solutions Pvt Ltd"
            return httpx.Response(200, json=sample_n8n_success_json)

        mock_transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=mock_transport) as mock_http_client:
            client = N8nClient(
                webhook_url="http://mock-n8n:5678/webhook/bid-verification",
                client=mock_http_client,
            )
            response = await client.trigger_verification(sample_n8n_payload)

            assert isinstance(response, N8nVerificationResponse)
            assert response.verification_id == "VER-TEST-001"
            assert response.decision == "QUALIFIED"
            assert response.risk_score == 12.5
            assert len(response.agent_results) == 2

    async def test_client_4xx_error_no_retry(self, sample_n8n_payload):
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(400, text="Bad Request: Missing required field")

        mock_transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=mock_transport) as mock_http_client:
            client = N8nClient(
                webhook_url="http://mock-n8n:5678/webhook/bid-verification",
                max_retries=3,
                client=mock_http_client,
            )

            with pytest.raises(N8nClientError) as exc_info:
                await client.trigger_verification(sample_n8n_payload)

            assert exc_info.value.status_code == 400
            assert call_count == 1  # Should fail immediately without retrying

    async def test_server_5xx_error_with_retries(self, sample_n8n_payload):
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(500, text="Internal Workflow Error")

        mock_transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=mock_transport) as mock_http_client:
            client = N8nClient(
                webhook_url="http://mock-n8n:5678/webhook/bid-verification",
                max_retries=2,
                client=mock_http_client,
            )

            with pytest.raises(N8nClientError) as exc_info:
                await client.trigger_verification(sample_n8n_payload)

            assert call_count == 2  # Retried max_retries times

    async def test_timeout_error_handling(self, sample_n8n_payload):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("Read timed out")

        mock_transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=mock_transport) as mock_http_client:
            client = N8nClient(
                webhook_url="http://mock-n8n:5678/webhook/bid-verification",
                max_retries=1,
                client=mock_http_client,
            )

            with pytest.raises(N8nTimeoutError):
                await client.trigger_verification(sample_n8n_payload)

    async def test_connection_error_handling(self, sample_n8n_payload):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        mock_transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=mock_transport) as mock_http_client:
            client = N8nClient(
                webhook_url="http://mock-n8n:5678/webhook/bid-verification",
                max_retries=1,
                client=mock_http_client,
            )

            with pytest.raises(N8nConnectionError):
                await client.trigger_verification(sample_n8n_payload)

    async def test_health_check(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "ok"})

        mock_transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=mock_transport) as mock_http_client:
            client = N8nClient(
                base_url="http://mock-n8n:5678",
                client=mock_http_client,
            )
            health = await client.check_health()
            assert health["reachable"] is True
            assert health["status_code"] == 200
