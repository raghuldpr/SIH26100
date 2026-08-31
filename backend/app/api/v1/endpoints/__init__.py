from app.api.v1.endpoints.audit import audit_router
from app.api.v1.endpoints.auth import auth_router
from app.api.v1.endpoints.bidders import bidders_router
from app.api.v1.endpoints.compliance import compliance_router
from app.api.v1.endpoints.documents import documents_router
from app.api.v1.endpoints.health import health_router
from app.api.v1.endpoints.tenders import tenders_router
from app.api.v1.endpoints.users import users_router
from app.api.v1.endpoints.verification import verification_router

__all__ = [
    "health_router",
    "auth_router",
    "users_router",
    "tenders_router",
    "bidders_router",
    "documents_router",
    "verification_router",
    "compliance_router",
    "audit_router",
]
