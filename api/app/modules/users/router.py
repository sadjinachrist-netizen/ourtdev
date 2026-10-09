"""Routes FastAPI — users / settings."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import AuthContext, CurrentAuth, DbSession, require_permission
from app.modules.users.schemas import (
    MeResponse,
    SiteSettingOut,
    SiteSettingUpdate,
    UsersStatus,
)
from app.modules.users.service import UsersService

router = APIRouter(tags=["users"])


@router.get("/users/me", response_model=MeResponse, summary="Compte courant")
async def me(auth: CurrentAuth, db: DbSession) -> MeResponse:
    return UsersService(db).me(auth)


@router.get("/settings", response_model=list[SiteSettingOut], tags=["settings"], summary="Paramètres publics")
async def list_public_settings(db: DbSession) -> list[SiteSettingOut]:
    return await UsersService(db).list_settings(include_all=False)


@router.get(
    "/settings/all",
    response_model=list[SiteSettingOut],
    tags=["settings"],
    summary="Tous les paramètres (admin)",
)
async def list_all_settings(
    db: DbSession,
    _auth: Annotated[AuthContext, Depends(require_permission("settings.manage"))],
) -> list[SiteSettingOut]:
    return await UsersService(db).list_settings(include_all=True)


@router.patch(
    "/settings/{key}",
    response_model=SiteSettingOut,
    tags=["settings"],
    summary="Modifier un paramètre",
)
async def update_setting(
    key: str,
    body: SiteSettingUpdate,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission("settings.manage"))],
) -> SiteSettingOut:
    return await UsersService(db).update_setting(
        key=key,
        value=body.value,
        description=body.description,
        auth=auth,
    )


@router.get("/users/status", response_model=UsersStatus, summary="Stub statut module users")
async def users_status() -> UsersStatus:
    return UsersStatus()
