import pytest
from fastapi import APIRouter, FastAPI, Query
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.core.exceptions import (
    AppException,
    BadRequestException,
    DatabaseException,
    NotFoundException,
    build_error_response,
)
from app.main import app

client = TestClient(app, raise_server_exceptions=False)


# Mock routes router to test validation and internal exceptions safely
_dummy_test_router = APIRouter(prefix="/test-reliability", tags=["test"])


class DummyPayload(BaseModel):
    name: str = Field(..., min_length=3)
    count: int = Field(..., ge=1, le=100)


@_dummy_test_router.post("/validate")
def dummy_validation_endpoint(payload: DummyPayload):
    return {"success": True, "data": payload.model_dump()}


@_dummy_test_router.get("/error/custom")
def dummy_custom_error():
    raise BadRequestException(message="Invalid query parameters supplied")


@_dummy_test_router.get("/error/notfound")
def dummy_not_found():
    raise NotFoundException(message="Item not found")


@_dummy_test_router.get("/error/database")
def dummy_db_error():
    raise DatabaseException(message="Database deadlock detected")


@_dummy_test_router.get("/error/unhandled")
def dummy_unhandled_error():
    raise ZeroDivisionError("division by zero test")


# Include the test router temporarily on the test app instance
app.include_router(_dummy_test_router)



def test_normal_request():
    """Verify normal requests succeed with 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_404_not_found_error_format():
    """Verify 404 error response matches standard error format."""
    response = client.get("/non-existent-endpoint-path")
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"
    assert "not found" in data["error"]["message"].lower()


def test_validation_error_format():
    """Verify 422 validation failure produces structured field error details."""
    response = client.post(
        "/test-reliability/validate",
        json={"name": "a", "count": 0},  # name too short (<3), count too low (<1)
    )
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert data["error"]["message"] == "Request validation failed."
    assert isinstance(data["error"]["details"], list)
    assert len(data["error"]["details"]) == 2

    fields = [d["field"] for d in data["error"]["details"]]
    assert "body.name" in fields
    assert "body.count" in fields


def test_missing_body_validation_error():
    """Verify missing body produces proper validation error response."""
    response = client.post("/test-reliability/validate", json={})
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert len(data["error"]["details"]) == 2


def test_custom_app_exceptions():
    """Verify custom managed app exceptions return expected status and code."""
    # Test BadRequestException (400)
    res_bad = client.get("/test-reliability/error/custom")
    assert res_bad.status_code == 400
    data_bad = res_bad.json()
    assert data_bad["success"] is False
    assert data_bad["error"]["code"] == "BAD_REQUEST"
    assert data_bad["error"]["message"] == "Invalid query parameters supplied"

    # Test NotFoundException (404)
    res_nf = client.get("/test-reliability/error/notfound")
    assert res_nf.status_code == 404
    data_nf = res_nf.json()
    assert data_nf["success"] is False
    assert data_nf["error"]["code"] == "NOT_FOUND"

    # Test DatabaseException (503)
    res_db = client.get("/test-reliability/error/database")
    assert res_db.status_code == 503
    data_db = res_db.json()
    assert data_db["success"] is False
    assert data_db["error"]["code"] == "DATABASE_ERROR"


def test_unhandled_internal_exception_sanitization():
    """Verify unhandled 500 exceptions do not leak stack traces or exception details to clients."""
    response = client.get("/test-reliability/error/unhandled")
    assert response.status_code == 500
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert data["error"]["message"] == "An unexpected internal server error occurred."
    # Ensure sensitive internal details (ZeroDivisionError) are not in the response payload
    assert "ZeroDivisionError" not in response.text
    assert "Traceback" not in response.text


def test_build_error_response_helper():
    """Verify build_error_response creates consistent error structure with and without details."""
    res_no_details = build_error_response(400, "BAD_INPUT", "Invalid value")
    import json
    body1 = json.loads(res_no_details.body.decode())
    assert body1 == {
        "success": False,
        "error": {
            "code": "BAD_INPUT",
            "message": "Invalid value",
        },
    }

    res_with_details = build_error_response(
        400, "BAD_INPUT", "Invalid value", details={"field": "email"}
    )
    body2 = json.loads(res_with_details.body.decode())
    assert body2 == {
        "success": False,
        "error": {
            "code": "BAD_INPUT",
            "message": "Invalid value",
            "details": {"field": "email"},
        },
    }
