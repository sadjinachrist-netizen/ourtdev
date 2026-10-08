"""Routes FastAPI — programs."""

from fastapi import APIRouter

from app.modules.programs.schemas import ProgramsStatus
from app.modules.programs.service import ProgramsService

router = APIRouter(prefix="/programs", tags=["programs"])
_service = ProgramsService()


@router.get("/status", response_model=ProgramsStatus, summary="Programmes, initiatives, chiffres clés")
async def programs_status() -> ProgramsStatus:
    """Stub : module monté, logique à venir (voir TODO.md)."""
    data = _service.status()
    return ProgramsStatus(**data)
