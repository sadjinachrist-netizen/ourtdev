"""Routes FastAPI — module 6 (ressources).
Public + admin, selon la permission demandée.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.resources.models import AccessLevel, ContentStatus, ResourceType
from app.modules.resources.schemas import (
    ResourceFolderOut,
    ResourceOut,
    ResourcesStatus,
)
from app.modules.resources.service import ResourcesService
from app.core.dependencies import CurrentAuth, get_current_user, require_permission

router = APIRouter(prefix="/resources", tags=["resources"])

_service = ResourcesService()


# --- Statut publique ---------------------------------------------------


@router.get("/status", response_model=ResourcesStatus, summary="Statut du module resources")
async def resources_status() -> ResourcesStatus:
    return _service.status()


# --- Dossiers ----------------------------------------------------------


@router.get(
    "/folders",
    response_model=list[ResourceFolderOut],
    summary="Liste des dossiers (filters)",
)
async def list_folders(
    auth: CurrentAuth,
    event_id: str | None = Query(default=None, alias="event_id"),
    program_id: str | None = Query(default=None, alias="program_id"),
    edition_year: int | None = Query(default=None, alias="edition_year"),
    access_level: AccessLevel | None = Query(default=None, alias="access_level"),
    status: ContentStatus | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    lang: str = Query(default="fr", alias="lang"),
) -> list[ResourceFolderOut]:
    trees = await _service.list_folders(
        db,
        event_id=event_id,
        program_id=program_id,
        edition_year=edition_year,
        access_level=access_level,
        status=status,
        user=auth.user,
        lang=lang,
    )
    return [t.to_dict() for t in trees]


# --- Ressources --------------------------------------------------------


@router.get(
    "/resources",
    response_model=list[ResourceOut],
    summary="Liste des ressources",
)
async def list_resources(
    auth: CurrentAuth,
    folder_id: str | None = Query(default=None, alias="folder_id"),
    type: ResourceType | None = Query(default=None, alias="type"),
    access_level: AccessLevel | None = Query(default=None, alias="access_level"),
    status: ContentStatus | None = Query(default=None, alias="status"),
    year: int | None = Query(default=None, alias="year"),
    event_id: str | None = Query(default=None, alias="event_id"),
    db: AsyncSession = Depends(get_db),
    lang: str = Query(default="fr", alias="lang"),
) -> list[ResourceOut]:
    return await _service.list_resources(
        db,
        folder_id=folder_id,
        type=type,
        access_level=access_level,
        status=status,
        year=year,
        event_id=event_id,
        user=auth.user,
        lang=lang,
    )


@router.post(
    "",
    response_model=ResourceOut,
    summary="Créer une ressource",
    dependencies=[Depends(require_permission("resource.manage"))],
)
async def create_resource(
    data: dict,
    auth: CurrentAuth,
    db: AsyncSession = Depends(get_db),
) -> ResourceOut:
    # TODO: implémenter la création (media upload + relations)
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented")


@router.delete(
    "/{resource_id}",
    response_model=dict,
    summary="Supprimer une ressource",
    dependencies=[Depends(require_permission("resource.manage"))],
)
async def delete_resource(
    resource_id: str,
    auth: CurrentAuth,
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    # TODO: implémenter la suppression
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented")
