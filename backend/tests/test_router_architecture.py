from fastapi.testclient import TestClient
from app.main import app
from app.schemas.common import (
    ErrorDetail,
    HealthResponse,
    PaginatedResponse,
    PaginationMeta,
    StandardErrorResponse,
    StandardResponse,
)

client = TestClient(app)


def test_api_v1_router_registration():
    """Verify that all v1 sub-routers and endpoints are registered."""
    from app.api.v1.router import api_v1_router
    from app.api.v1.endpoints import (
        audit_router,
        auth_router,
        bidders_router,
        compliance_router,
        documents_router,
        health_router,
        tenders_router,
        users_router,
        verification_router,
    )

    # Verify all 8 modular routers and health router exist
    sub_routers = [
        health_router,
        auth_router,
        users_router,
        tenders_router,
        bidders_router,
        documents_router,
        verification_router,
        compliance_router,
        audit_router,
    ]
    for r in sub_routers:
        assert r is not None

    # Verify live HTTP responses for root, health, and v1 health endpoints
    res_root = client.get("/")
    assert res_root.status_code == 200

    res_health = client.get("/health")
    assert res_health.status_code == 200

    res_v1_health = client.get("/api/v1/health")
    assert res_v1_health.status_code == 200

    res_v1_health_db = client.get("/api/v1/health/db")
    assert res_v1_health_db.status_code == 200




def test_api_v1_openapi_generation():
    """Verify OpenAPI schema generates with correct tags and routes."""
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    openapi_data = response.json()

    assert openapi_data["openapi"].startswith("3.")
    assert openapi_data["info"]["title"] == "SIH26100"
    assert "/api/v1/health" in openapi_data["paths"]
    assert "/api/v1/health/db" in openapi_data["paths"]


def test_response_schemas_conventions():
    """Verify standard response schema models instantiate properly."""
    # Test StandardResponse
    success_resp = StandardResponse[dict](
        success=True,
        data={"key": "value"},
        message="Operation completed",
    )
    assert success_resp.success is True
    assert success_resp.data == {"key": "value"}
    assert success_resp.message == "Operation completed"

    # Test StandardErrorResponse
    error_resp = StandardErrorResponse(
        success=False,
        error={
            "code": "BAD_REQUEST",
            "message": "Invalid input",
            "details": [
                ErrorDetail(field="email", message="Invalid email format", type="value_error")
            ],
        },
    )
    assert error_resp.success is False
    assert error_resp.error.code == "BAD_REQUEST"
    assert len(error_resp.error.details) == 1
    assert error_resp.error.details[0].field == "email"

    # Test PaginatedResponse
    paginated_resp = PaginatedResponse[str](
        success=True,
        data=["item1", "item2"],
        pagination=PaginationMeta(
            total_count=100,
            page=1,
            page_size=2,
            total_pages=50,
        ),
    )
    assert paginated_resp.pagination.total_count == 100
    assert len(paginated_resp.data) == 2


def test_health_response_schema():
    """Verify HealthResponse model serialization."""
    hr = HealthResponse(
        status="healthy",
        api_version="v1",
        environment="development",
        database="connected",
    )
    data = hr.model_dump()
    assert data["status"] == "healthy"
    assert data["api_version"] == "v1"
    assert data["environment"] == "development"
    assert data["database"] == "connected"
