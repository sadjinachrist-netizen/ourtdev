"""Routes FastAPI — contents."""

from fastapi import APIRouter

from app.modules.contents.schemas import ContentsStatus
from app.modules.contents.service import ContentsService

router = APIRouter(prefix="/contents", tags=["contents"])
_service = ContentsService()


@router.get("/status", response_model=ContentsStatus, summary="Pages, articles, partenaires, contact")
async def contents_status() -> ContentsStatus:
    """Stub : module monté, logique à venir (voir TODO.md)."""
    data = _service.status()
    return ContentsStatus(**data)
