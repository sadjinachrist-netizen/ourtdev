"""Routes FastAPI — users."""

from fastapi import APIRouter

from app.modules.users.schemas import UsersStatus
from app.modules.users.service import UsersService

router = APIRouter(prefix="/users", tags=["users"])
_service = UsersService()


@router.get("/status", response_model=UsersStatus, summary="Comptes, rôles et permissions")
async def users_status() -> UsersStatus:
    """Stub : module monté, logique à venir (voir TODO.md)."""
    data = _service.status()
    return UsersStatus(**data)
