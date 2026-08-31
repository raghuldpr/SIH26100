from fastapi import APIRouter

bidders_router = APIRouter(
    prefix="/bidders",
    tags=["bidders"],
)
