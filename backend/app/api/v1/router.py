from fastapi import APIRouter

from app.api.v1.endpoints.audit import audit_router
from app.api.v1.endpoints.auth import auth_router
from app.api.v1.endpoints.bidders import bidders_router
from app.api.v1.endpoints.compliance import compliance_router
from app.api.v1.endpoints.documents import documents_router
from app.api.v1.endpoints.health import health_router
from app.api.v1.endpoints.tenders import tenders_router
from app.api.v1.endpoints.users import users_router
from app.api.v1.endpoints.verification import verification_router

# Central API v1 Router
api_v1_router = APIRouter()

# Register core health & diagnostic endpoints
api_v1_router.include_router(health_router)

# Register modular sub-routers for future capability phases
api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(tenders_router)
api_v1_router.include_router(bidders_router)
api_v1_router.include_router(documents_router)
api_v1_router.include_router(verification_router)
api_v1_router.include_router(compliance_router)
api_v1_router.include_router(audit_router)
