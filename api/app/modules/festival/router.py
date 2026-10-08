"""Routes FastAPI — festival."""

from fastapi import APIRouter

from app.modules.festival.schemas import FestivalStatus
from app.modules.festival.service import FestivalService

router = APIRouter(prefix="/festival", tags=["festival"])
_service = FestivalService()


@router.get("/status", response_model=FestivalStatus, summary="Éditions Festival, annonces, redirects")
async def festival_status() -> FestivalStatus:
    """Stub : module monté, logique à venir (voir TODO.md)."""
    data = _service.status()
    return FestivalStatus(**data)
