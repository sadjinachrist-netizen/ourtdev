"""Routes FastAPI — events."""

from fastapi import APIRouter

from app.modules.events.schemas import EventsStatus
from app.modules.events.service import EventsService

router = APIRouter(prefix="/events", tags=["events"])
_service = EventsService()


@router.get("/status", response_model=EventsStatus, summary="Événements et meetups")
async def events_status() -> EventsStatus:
    """Stub : module monté, logique à venir (voir TODO.md)."""
    data = _service.status()
    return EventsStatus(**data)
