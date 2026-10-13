"""Routes publiques du festival."""

from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse

from app.core.dependencies import DbSession, Language
from app.modules.festival import edition_read
from app.modules.festival import announcements as announcement_api
from app.modules.festival import redirects as redirect_api
from app.modules.festival.schemas import AnnouncementOut, EditionOut, FestivalPage, FestivalStatus

router = APIRouter(tags=["festival"])


@router.get("/festival/status", response_model=FestivalStatus, summary="Statut module festival")
async def festival_status() -> FestivalStatus:
    return FestivalStatus()


@router.get("/festival/announcements", response_model=list[AnnouncementOut], summary="Bandeau d'annonces")
async def list_announcements(db: DbSession, lang: Language) -> list[AnnouncementOut]:
    return await announcement_api.active_announcements(db, lang)


@router.get("/festival/current", response_model=EditionOut, summary="Édition en cours")
async def current_edition(db: DbSession, lang: Language) -> EditionOut:
    return await edition_read.get_current(db, lang)


@router.get("/festival", response_model=FestivalPage, summary="Édition en cours et archive")
async def festival_page(db: DbSession, lang: Language) -> FestivalPage:
    return await edition_read.list_public(db, lang)


@router.get("/festival/{year}/go", summary="Redirection vers le lien de l'édition")
async def festival_go(year: int, db: DbSession) -> RedirectResponse:
    target, code = await edition_read.go(db, year)
    return RedirectResponse(url=target, status_code=code)


@router.get("/festival/{year}", response_model=EditionOut, summary="Édition par année")
async def festival_year(year: int, db: DbSession, lang: Language) -> EditionOut:
    return await edition_read.get_public(db, year, lang)


@router.get("/redirects/resolve", summary="Résoudre une redirection et compter le hit")
async def resolve_redirect(
    db: DbSession,
    path: Annotated[str, Query(description="Chemin source, ex. /festival/2026")],
) -> RedirectResponse:
    target, code = await redirect_api.resolve(db, path)
    return RedirectResponse(url=target, status_code=code)
