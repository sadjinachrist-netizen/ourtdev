"""Routes FastAPI — resources."""

from fastapi import APIRouter

from app.modules.resources.schemas import ResourcesStatus
from app.modules.resources.service import ResourcesService

router = APIRouter(prefix="/resources", tags=["resources"])
_service = ResourcesService()


@router.get("/status", response_model=ResourcesStatus, summary="Dossiers et ressources partagées")
async def resources_status() -> ResourcesStatus:
    """Stub : module monté, logique à venir (voir TODO.md)."""
    data = _service.status()
    return ResourcesStatus(**data)
