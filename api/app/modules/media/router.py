"""Routes FastAPI — media."""

from fastapi import APIRouter

from app.modules.media.schemas import MediaStatus
from app.modules.media.service import MediaService

router = APIRouter(prefix="/media", tags=["media"])
_service = MediaService()


@router.get("/status", response_model=MediaStatus, summary="Médiathèque")
async def media_status() -> MediaStatus:
    """Stub : module monté, logique à venir (voir TODO.md)."""
    data = _service.status()
    return MediaStatus(**data)
