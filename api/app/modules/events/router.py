"""Routes FastAPI — événements et meetups (module 3)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

from app.core.dependencies import AuthContext, CurrentAuth, DbSession, Language, require_permission
from app.modules.events.schemas import (
    EventCreate,
    EventListItem,
    EventMediaCreate,
    EventOut,
    EventPartnerAttach,
    EventSpeakerAttach,
    EventUpdate,
    EventsStatus,
    IdOut,
    RegisterRequest,
    SpeakerCreate,
    WhenLiteral,
)
from app.modules.events.service import EventsService
from app.shared.pagination import Page, PageParams, page_params
from app.shared.schemas import Message

router = APIRouter(tags=["events"])


def _service(db: DbSession) -> EventsService:
    return EventsService(db)


async def require_event_writer(auth: CurrentAuth) -> AuthContext:
    if auth.has_permission("event.manage") or auth.has_permission("event.propose"):
        return auth
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"detail": "Permission requise: event.propose", "code": "forbidden"},
    )


EventWriter = Annotated[AuthContext, Depends(require_event_writer)]


@router.get("/events/status", response_model=EventsStatus, summary="Statut module events")
async def events_status(db: DbSession) -> EventsStatus:
    return EventsStatus(**_service(db).status())


@router.get("/events/timeline", response_model=list[EventListItem], summary="Frise chronologique")
async def timeline(db: DbSession, lang: Language) -> list[EventListItem]:
    return await _service(db).timeline(lang)


@router.get("/events", response_model=Page[EventListItem], summary="Liste des événements publiés")
async def list_events(
    db: DbSession,
    lang: Language,
    params: Annotated[PageParams, Depends(page_params)],
    when: Annotated[WhenLiteral, Query()] = "upcoming",
    type: Annotated[str | None, Query()] = None,
    year: Annotated[int | None, Query()] = None,
    city: Annotated[str | None, Query()] = None,
    format: Annotated[str | None, Query(alias="format")] = None,
) -> Page[EventListItem]:
    return await _service(db).list_public(
        lang=lang,
        when=when,
        event_type=type,
        year=year,
        city=city,
        event_format=format,
        params=params,
    )


@router.get("/events/{slug}/calendar.ics", summary="Export calendrier")
async def calendar_ics(slug: str, db: DbSession, lang: Language) -> Response:
    body = await _service(db).calendar_ics(slug, lang)
    return Response(
        content=body,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="{slug}.ics"'},
    )


@router.post(
    "/events/{slug}/register",
    response_model=Message,
    status_code=status.HTTP_201_CREATED,
    summary="S'inscrire à un événement",
)
async def register_event(
    slug: str,
    db: DbSession,
    auth: CurrentAuth,
    body: RegisterRequest | None = None,
) -> Message:
    await _service(db).register(slug, body or RegisterRequest(), auth)
    return Message(detail="Inscription enregistrée", code="event_registered")


@router.get("/events/{slug}", response_model=EventOut, summary="Fiche événement")
async def get_event(slug: str, db: DbSession, lang: Language) -> EventOut:
    return await _service(db).get_public(slug, lang)


@router.post(
    "/admin/events",
    response_model=EventOut,
    status_code=status.HTTP_201_CREATED,
    summary="Proposer ou créer un événement",
)
async def create_event(
    body: EventCreate,
    db: DbSession,
    auth: EventWriter,
    lang: Language,
) -> EventOut:
    return await _service(db).create(body, auth, lang)


@router.patch("/admin/events/{event_id}", response_model=EventOut, summary="Modifier un événement")
async def update_event(
    event_id: uuid.UUID,
    body: EventUpdate,
    db: DbSession,
    auth: EventWriter,
    lang: Language,
) -> EventOut:
    return await _service(db).update(event_id, body, auth, lang)


@router.post(
    "/admin/events/{event_id}/publish",
    response_model=EventOut,
    summary="Publier un événement",
)
async def publish_event(
    event_id: uuid.UUID,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission("event.manage"))],
    lang: Language,
) -> EventOut:
    return await _service(db).publish(event_id, auth, lang)


@router.post(
    "/admin/speakers",
    response_model=IdOut,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un intervenant",
)
async def create_speaker(body: SpeakerCreate, db: DbSession, auth: EventWriter) -> IdOut:
    speaker_id = await _service(db).create_speaker(body, auth)
    return IdOut(id=speaker_id)


@router.post(
    "/admin/events/{event_id}/speakers",
    response_model=EventOut,
    summary="Associer un intervenant",
)
async def attach_speaker(
    event_id: uuid.UUID,
    body: EventSpeakerAttach,
    db: DbSession,
    auth: EventWriter,
    lang: Language,
) -> EventOut:
    return await _service(db).attach_speaker(event_id, body, auth, lang)


@router.post(
    "/admin/events/{event_id}/media",
    response_model=EventOut,
    summary="Ajouter une photo ou une vidéo",
)
async def add_media(
    event_id: uuid.UUID,
    body: EventMediaCreate,
    db: DbSession,
    auth: EventWriter,
    lang: Language,
) -> EventOut:
    return await _service(db).add_media(event_id, body, auth, lang)


@router.post(
    "/admin/events/{event_id}/partners",
    response_model=EventOut,
    summary="Associer un partenaire",
)
async def attach_partner(
    event_id: uuid.UUID,
    body: EventPartnerAttach,
    db: DbSession,
    auth: EventWriter,
    lang: Language,
) -> EventOut:
    return await _service(db).attach_partner(event_id, body, auth, lang)
