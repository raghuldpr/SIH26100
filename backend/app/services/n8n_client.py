"""
Phase 10 — n8n Master Orchestrator Client Service
services/n8n_client.py: Asynchronous HTTP client for communicating with n8n multi-agent workflows.

Provides:
- Resilient asynchronous dispatch via httpx with connection pooling
- HMAC-SHA256 signature generation and verification for webhook security
- Exponential backoff retry logic with jitter
- Strong typing with N8nVerificationPayload and N8nVerificationResponse
- Comprehensive error handling and logging
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import time
from typing import Any, Dict, Optional, Union
import uuid

import httpx

from app.config import settings
from app.schemas.verification import (
    N8nAgentResult,
    N8nVerificationPayload,
    N8nVerificationResponse,
)

logger = logging.getLogger("app.services.n8n_client")


class N8nClientError(Exception):
    """Base exception for n8n client operations."""

    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class N8nTimeoutError(N8nClientError):
    """Raised when n8n webhook request times out."""
    pass


class N8nConnectionError(N8nClientError):
    """Raised when connection to n8n fails."""
    pass


class N8nClient:
    """
    Asynchronous client for interacting with n8n Master Orchestrator and verification agents.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        webhook_url: Optional[str] = None,
        api_key: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.base_url = (base_url or settings.N8N_BASE_URL).rstrip("/")
        self.webhook_url = webhook_url or settings.N8N_WEBHOOK_URL
        self.api_key = api_key or settings.N8N_API_KEY
        self.webhook_secret = webhook_secret or settings.N8N_WEBHOOK_SECRET
        self.timeout = timeout if timeout is not None else settings.N8N_TIMEOUT_SECONDS
        self.max_retries = max_retries if max_retries is not None else settings.N8N_MAX_RETRIES
        self._external_client = client

    def generate_signature(self, body: Union[bytes, str]) -> str:
        """
        Generates an HMAC-SHA256 signature for outgoing and incoming payloads.
        """
        if isinstance(body, str):
            body = body.encode("utf-8")
        secret = self.webhook_secret.encode("utf-8")
        return hmac.new(secret, body, hashlib.sha256).hexdigest()

    def verify_webhook_signature(self, body: Union[bytes, str], signature: str) -> bool:
        """
        Verifies incoming webhook signature using constant-time comparison.
        """
        if not signature or not self.webhook_secret:
            return False
        expected_sig = self.generate_signature(body)
        # Strip optional sha256= prefix if present
        clean_sig = signature.replace("sha256=", "").strip()
        return hmac.compare_digest(expected_sig, clean_sig)

    def get_auth_headers(self, body: Optional[Union[bytes, str]] = None) -> Dict[str, str]:
        """
        Constructs standard security and authentication headers for n8n requests.
        """
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"{settings.APP_NAME}-FastAPI-n8n-Client/{settings.VERSION}",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["X-N8N-API-KEY"] = self.api_key
        if self.webhook_secret:
            headers["X-Webhook-Secret"] = self.webhook_secret
            if body is not None:
                headers["X-Webhook-Signature"] = f"sha256={self.generate_signature(body)}"
        return headers

    async def trigger_verification(
        self,
        payload: Union[N8nVerificationPayload, Dict[str, Any]],
        request_id: Optional[str] = None,
    ) -> N8nVerificationResponse:
        """
        Dispatches a verification request payload to the n8n Master Orchestrator webhook.
        Handles retries with exponential backoff for transient failures.
        """
        if isinstance(payload, dict):
            validated_payload = N8nVerificationPayload.model_validate(payload)
        else:
            validated_payload = payload

        req_id = request_id or validated_payload.request_id
        serialized_json = validated_payload.model_dump_json()
        headers = self.get_auth_headers(body=serialized_json)

        logger.info(
            f"[n8n-dispatch] Dispatched verification request {req_id} for bidder "
            f"'{validated_payload.bidder_name}' to {self.webhook_url}"
        )

        last_exception: Optional[Exception] = None
        backoff_delay = 1.0

        for attempt in range(1, self.max_retries + 1):
            start_time = time.time()
            try:
                if self._external_client:
                    response = await self._external_client.post(
                        self.webhook_url,
                        content=serialized_json,
                        headers=headers,
                        timeout=self.timeout,
                    )
                else:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.post(
                            self.webhook_url,
                            content=serialized_json,
                            headers=headers,
                        )

                duration = time.time() - start_time
                logger.info(
                    f"[n8n-response] Request {req_id} attempt {attempt}/{self.max_retries} "
                    f"returned HTTP {response.status_code} in {duration:.2f}s"
                )

                if response.status_code == 200:
                    data = response.json()
                    return N8nVerificationResponse.model_validate(data)

                # If n8n returned a 4xx client error, don't retry, fail immediately
                if 400 <= response.status_code < 500:
                    error_msg = f"n8n webhook rejected request with HTTP {response.status_code}: {response.text}"
                    logger.error(f"[n8n-error] {error_msg}")
                    raise N8nClientError(error_msg, status_code=response.status_code, details={"response": response.text})

                # Server error 5xx: candidate for retry
                error_msg = f"n8n webhook failed with HTTP {response.status_code}: {response.text}"
                logger.warning(f"[n8n-warning] {error_msg} (Attempt {attempt}/{self.max_retries})")
                last_exception = N8nClientError(error_msg, status_code=response.status_code)

            except httpx.TimeoutException as exc:
                duration = time.time() - start_time
                logger.warning(
                    f"[n8n-timeout] Attempt {attempt}/{self.max_retries} timed out after {duration:.2f}s: {exc}"
                )
                last_exception = N8nTimeoutError(f"Request to n8n webhook timed out after {self.timeout}s: {exc}")

            except httpx.RequestError as exc:
                logger.warning(
                    f"[n8n-connection-error] Attempt {attempt}/{self.max_retries} failed to connect: {exc}"
                )
                last_exception = N8nConnectionError(f"Failed to connect to n8n webhook: {exc}")

            except N8nClientError:
                raise

            except Exception as exc:
                logger.error(f"[n8n-unexpected-error] Unexpected error during n8n dispatch: {exc}")
                last_exception = N8nClientError(f"Unexpected error communicating with n8n: {exc}")

            if attempt < self.max_retries:
                await asyncio.sleep(backoff_delay)
                backoff_delay *= 2.0

        # All retries exhausted
        if isinstance(last_exception, N8nClientError):
            raise last_exception
        raise N8nClientError(f"Failed to execute n8n verification after {self.max_retries} attempts: {last_exception}")

    async def check_health(self) -> Dict[str, Any]:
        """
        Checks connectivity to n8n instance.
        """
        health_url = f"{self.base_url}/healthz"
        try:
            if self._external_client:
                resp = await self._external_client.get(health_url, timeout=5.0)
            else:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(health_url)
            return {
                "reachable": resp.status_code in (200, 401, 403, 404),
                "status_code": resp.status_code,
                "base_url": self.base_url,
            }
        except Exception as exc:
            return {
                "reachable": False,
                "error": str(exc),
                "base_url": self.base_url,
            }


# Singleton instance for dependency injection
n8n_client = N8nClient()
