"""Routes d'administration du festival et des redirections."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.dependencies import AuthContext, DbSession, Language, require_permission
from app.modules.festival import announcements as announcement_api
from app.modules.festival import edition_write
from app.modules.festival import redirects as redirect_api
from app.modules.festival.schemas import (
    AnnouncementCreate,
    AnnouncementOut,
    AnnouncementUpdate,
    EditionCreate,
    EditionOut,
    EditionUpdate,
    FigureCreate,
    RedirectCreate,
    RedirectOut,
    RedirectUpdate,
)

router = APIRouter(tags=["festival"])


@router.post(
    "/admin/festival/editions",
    response_model=EditionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une édition",
)
async def create_edition(
    body: EditionCreate,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission("festival.manage"))],
    lang: Language,
) -> EditionOut:
    return await edition_write.create_edition(db, body, auth, lang)


@router.patch(
    "/admin/festival/editions/{year}",
    response_model=EditionOut,
    summary="Modifier une édition, dont target_url",
)
async def update_edition(
    year: int,
    body: EditionUpdate,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission("festival.manage"))],
    lang: Language,
) -> EditionOut:
    return await edition_write.update_edition(db, year, body, auth, lang)


@router.post(
    "/admin/festival/editions/{year}/publish",
    response_model=EditionOut,
    summary="Publier une édition",
)
async def publish_edition(
    year: int,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission("festival.manage"))],
    lang: Language,
) -> EditionOut:
    return await edition_write.publish_edition(db, year, auth, lang)


@router.post(
    "/admin/festival/editions/{year}/figures",
    response_model=EditionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Ajouter un chiffre à une édition",
)
async def add_figure(
    year: int,
    body: FigureCreate,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission("festival.manage"))],
    lang: Language,
) -> EditionOut:
    return await edition_write.add_figure(db, year, body, auth, lang)


@router.post(
    "/admin/festival/announcements",
    response_model=AnnouncementOut,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une annonce",
)
async def create_announcement(
    body: AnnouncementCreate,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission("festival.manage"))],
    lang: Language,
) -> AnnouncementOut:
    return await announcement_api.create_announcement(db, body, auth, lang)


@router.patch(
    "/admin/festival/announcements/{announcement_id}",
    response_model=AnnouncementOut,
    summary="Modifier une annonce",
)
async def update_announcement(
    announcement_id: uuid.UUID,
    body: AnnouncementUpdate,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission("festival.manage"))],
    lang: Language,
) -> AnnouncementOut:
    return await announcement_api.update_announcement(db, announcement_id, body, auth, lang)


@router.get("/admin/redirects", response_model=list[RedirectOut], summary="Lister les redirections")
async def list_redirects(
    db: DbSession,
    _auth: Annotated[AuthContext, Depends(require_permission("settings.manage"))],
) -> list[RedirectOut]:
    return await redirect_api.list_redirects(db)


@router.post(
    "/admin/redirects",
    response_model=RedirectOut,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une redirection",
)
async def create_redirect(
    body: RedirectCreate,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission("settings.manage"))],
) -> RedirectOut:
    return await redirect_api.create_redirect(db, body, auth)


@router.patch("/admin/redirects/{redirect_id}", response_model=RedirectOut, summary="Modifier une redirection")
async def update_redirect(
    redirect_id: int,
    body: RedirectUpdate,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission("settings.manage"))],
) -> RedirectOut:
    return await redirect_api.update_redirect(db, redirect_id, body, auth)
