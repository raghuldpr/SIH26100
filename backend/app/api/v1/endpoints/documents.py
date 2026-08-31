from fastapi import APIRouter

documents_router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)
