"""Routes FastAPI — members."""

from fastapi import APIRouter

from app.modules.members.schemas import MembersStatus
from app.modules.members.service import MembersService

router = APIRouter(prefix="/members", tags=["members"])
_service = MembersService()


@router.get("/status", response_model=MembersStatus, summary="Profils, annuaire, PII, messages")
async def members_status() -> MembersStatus:
    """Stub : module monté, logique à venir (voir TODO.md)."""
    data = _service.status()
    return MembersStatus(**data)
