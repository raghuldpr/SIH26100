from fastapi import APIRouter

audit_router = APIRouter(
    prefix="/audit",
    tags=["audit"],
)
