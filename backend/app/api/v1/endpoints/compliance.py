from fastapi import APIRouter

compliance_router = APIRouter(
    prefix="/compliance",
    tags=["compliance"],
)
