"""Routes FastAPI — auth."""

from fastapi import APIRouter

from app.modules.auth.schemas import AuthStatus
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
_service = AuthService()


@router.get("/status", response_model=AuthStatus, summary="Authentification (register, login, OAuth, MFA)")
async def auth_status() -> AuthStatus:
    """Stub : module monté, logique à venir (voir TODO.md)."""
    data = _service.status()
    return AuthStatus(**data)
