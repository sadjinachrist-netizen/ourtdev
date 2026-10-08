"""Routes FastAPI — projects."""

from fastapi import APIRouter

from app.modules.projects.schemas import ProjectsStatus
from app.modules.projects.service import ProjectsService

router = APIRouter(prefix="/projects", tags=["projects"])
_service = ProjectsService()


@router.get("/status", response_model=ProjectsStatus, summary="Projets open source")
async def projects_status() -> ProjectsStatus:
    """Stub : module monté, logique à venir (voir TODO.md)."""
    data = _service.status()
    return ProjectsStatus(**data)
