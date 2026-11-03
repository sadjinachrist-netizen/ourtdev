"""Logique métier — événements et meetups (module 3)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import extract, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import AuthContext
from app.modules.contents.models import ContentStatus, Partner
from app.modules.events.models import (
    Event,
    EventFormat,
    EventMedia,
    EventParticipant,
    EventPartner,
    EventSpeaker,
    EventTranslation,
    EventType,
    Speaker,
    SpeakerTranslation,
)
from app.modules.events.schemas import (
    EventCreate,
    EventListItem,
    EventMediaCreate,
    EventOut,
    EventPartnerAttach,
    EventSpeakerAttach,
    EventUpdate,
    RegisterRequest,
    ResourceFolderLink,
    SpeakerCreate,
    SpeakerOut,
    EventMediaOut,
    EventPartnerOut,
)
from app.shared.activity import log_activity
from app.shared.i18n import pick_translation
from app.shared.pagination import Page, PageParams
from app.shared.publishing import now_utc, published_filter


class EventsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def status(self) -> dict[str, str]:
        return {"module": "events", "status": "ready"}

    def _manages(self, auth: AuthContext) -> bool:
        return auth.has_permission("event.manage")

    def _assert_writer(self, auth: AuthContext) -> None:
        if self._manages(auth) or auth.has_permission("event.propose"):
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "Permission requise: event.manage", "code": "forbidden"},
        )

    async def _community_exists(self, community_id: int | None) -> None:
        if community_id is None:
            return
        found = (
            await self.db.execute(
                text("SELECT 1 FROM communities WHERE id = :id"),
                {"id": community_id},
            )
        ).scalar()
        if found is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "Communauté inconnue", "code": "unknown_community"},
            )

    async def _edition_exists(self, year: int | None) -> None:
        if year is None:
            return
        found = (
            await self.db.execute(
                text("SELECT 1 FROM festival_editions WHERE year = :year"),
                {"year": year},
            )
        ).scalar()
        if found is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "Édition inconnue", "code": "unknown_edition"},
            )

    def _scoped_community(self, auth: AuthContext, community_id: int | None) -> int | None:
        if self._manages(auth):
            return community_id
        allowed = auth.community_ids
        if community_id is None:
            if len(allowed) != 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "detail": "community_id requis pour un lead",
                        "code": "community_required",
                    },
                )
            return allowed[0]
        if community_id not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"detail": "Événement hors de votre communauté", "code": "community_forbidden"},
            )
        return community_id

    def _assert_can_edit(self, auth: AuthContext, event: Event) -> None:
        if self._manages(auth):
            return
        if event.community_id not in auth.community_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"detail": "Événement hors de votre communauté", "code": "community_forbidden"},
            )

    async def _replace_translations(self, event_id: uuid.UUID, items: list) -> None:
        rows = (
            await self.db.execute(
                select(EventTranslation).where(EventTranslation.event_id == event_id)
            )
        ).scalars().all()
        existing = {row.language_code: row for row in rows}
        for tr in items:
            current = existing.get(tr.language_code)
            if current is None:
                self.db.add(
                    EventTranslation(
                        event_id=event_id,
                        language_code=tr.language_code,
                        title=tr.title,
                        summary=tr.summary,
                        description=tr.description,
                        meta_title=tr.meta_title,
                        meta_description=tr.meta_description,
                    )
                )
            else:
                current.title = tr.title
                current.summary = tr.summary
                current.description = tr.description
                current.meta_title = tr.meta_title
                current.meta_description = tr.meta_description

    async def _ensure_resource_folder(self, event: Event, actor_id: uuid.UUID) -> None:
        await self.db.flush()
        found = (
            await self.db.execute(
                text("SELECT id FROM resource_folders WHERE event_id = :eid LIMIT 1"),
                {"eid": event.id},
            )
        ).first()
        if found is not None:
            return
        folder_id = uuid.uuid4()
        slug = event.slug
        clash = (
            await self.db.execute(
                text(
                    """
                    SELECT 1 FROM resource_folders
                    WHERE parent_id IS NULL AND slug = :slug
                    """
                ),
                {"slug": slug},
            )
        ).first()
        if clash is not None:
            slug = f"{event.slug}-{folder_id.hex[:6]}"
        await self.db.execute(
            text(
                """
                INSERT INTO resource_folders
                  (id, slug, event_id, community_id, access_level, status, published_at, created_by)
                VALUES
                  (:id, :slug, :event_id, :community_id,
                   'public'::access_level, 'published'::content_status, now(), :created_by)
                """
            ),
            {
                "id": folder_id,
                "slug": slug,
                "event_id": event.id,
                "community_id": event.community_id,
                "created_by": actor_id,
            },
        )
        translations = (
            await self.db.execute(
                select(EventTranslation).where(EventTranslation.event_id == event.id)
            )
        ).scalars().all()
        for tr in translations:
            await self.db.execute(
                text(
                    """
                    INSERT INTO resource_folder_translations
                      (folder_id, language_code, name, description)
                    VALUES (:folder_id, :language_code, :name, :description)
                    """
                ),
                {
                    "folder_id": folder_id,
                    "language_code": tr.language_code,
                    "name": tr.title,
                    "description": tr.summary,
                },
            )

    async def _folder_link(self, event_id: uuid.UUID) -> ResourceFolderLink | None:
        row = (
            await self.db.execute(
                text(
                    """
                    SELECT id, slug FROM resource_folders
                    WHERE event_id = :eid AND status = 'published'
                    ORDER BY created_at
                    LIMIT 1
                    """
                ),
                {"eid": event_id},
            )
        ).first()
        if row is None:
            return None
        return ResourceFolderLink(id=row[0], slug=row[1])

    def _list_item(self, event: Event, lang: str) -> EventListItem | None:
        tr = pick_translation(event.translations, lang)
        if tr is None:
            return None
        return EventListItem(
            id=event.id,
            slug=event.slug,
            type=event.type.value,
            format=event.format.value,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
            city=event.city,
            venue=event.venue,
            language=tr.language_code,
            title=tr.title,
            summary=tr.summary,
            show_in_timeline=event.show_in_timeline,
        )

    async def _speakers(self, event_id: uuid.UUID, lang: str) -> list[SpeakerOut]:
        rows = (
            await self.db.execute(
                select(EventSpeaker, Speaker)
                .join(Speaker, Speaker.id == EventSpeaker.speaker_id)
                .where(EventSpeaker.event_id == event_id)
                .options(selectinload(Speaker.translations))
                .order_by(EventSpeaker.position, Speaker.full_name)
            )
        ).all()
        result: list[SpeakerOut] = []
        for link, speaker in rows:
            tr = pick_translation(speaker.translations, lang)
            result.append(
                SpeakerOut(
                    id=speaker.id,
                    full_name=speaker.full_name,
                    role=link.role,
                    organization=speaker.organization,
                    job_title=tr.job_title if tr else None,
                    bio=tr.bio if tr else None,
                    linkedin_url=speaker.linkedin_url,
                    github_url=speaker.github_url,
                    website_url=speaker.website_url,
                    position=link.position,
                )
            )
        return result

    async def _partners(self, event_id: uuid.UUID) -> list[EventPartnerOut]:
        rows = (
            await self.db.execute(
                select(Partner)
                .join(EventPartner, EventPartner.partner_id == Partner.id)
                .where(EventPartner.event_id == event_id)
                .order_by(Partner.name)
            )
        ).scalars().all()
        return [EventPartnerOut(id=p.id, slug=p.slug, name=p.name) for p in rows]

    async def _gallery(self, event_id: uuid.UUID) -> list[EventMediaOut]:
        rows = (
            await self.db.execute(
                select(EventMedia)
                .where(EventMedia.event_id == event_id)
                .order_by(EventMedia.position, EventMedia.created_at)
            )
        ).scalars().all()
        return [
            EventMediaOut(id=row.id, kind=row.kind, media_id=row.media_id, url=row.url, position=row.position)
            for row in rows
        ]

    async def _to_out(self, event: Event, lang: str) -> EventOut:
        item = self._list_item(event, lang)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Traduction manquante", "code": "translation_missing"},
            )
        tr = pick_translation(event.translations, lang)
        show = event.show_stats
        return EventOut(
            **item.model_dump(),
            timezone=event.timezone,
            country_code=event.country_code,
            online_url=event.online_url,
            registration_url=event.registration_url,
            replay_url=event.replay_url,
            description=tr.description if tr else None,
            community_id=event.community_id,
            edition_year=event.edition_year,
            status=event.status.value,
            published_at=event.published_at,
            show_stats=show,
            participants_count=event.participants_count if show else None,
            sessions_count=event.sessions_count if show else None,
            speakers=await self._speakers(event.id, lang),
            partners=await self._partners(event.id),
            gallery=await self._gallery(event.id),
            resource_folder=await self._folder_link(event.id),
        )

    async def _get(self, event_id: uuid.UUID) -> Event:
        event = (
            await self.db.execute(
                select(Event).where(Event.id == event_id).options(selectinload(Event.translations))
            )
        ).scalar_one_or_none()
        if event is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Événement introuvable", "code": "event_not_found"},
            )
        return event

    async def list_public(
        self,
        *,
        lang: str,
        when: str,
        event_type: str | None,
        year: int | None,
        city: str | None,
        event_format: str | None,
        params: PageParams,
    ) -> Page[EventListItem]:
        stmt = select(Event).where(published_filter(Event.status, Event.published_at))
        now = now_utc()
        if when == "upcoming":
            stmt = stmt.where(Event.starts_at >= now)
        elif when == "past":
            stmt = stmt.where(Event.starts_at < now)
        if event_type:
            stmt = stmt.where(Event.type == EventType(event_type))
        if event_format:
            stmt = stmt.where(Event.format == EventFormat(event_format))
        if year is not None:
            stmt = stmt.where(extract("year", Event.starts_at) == year)
        if city:
            stmt = stmt.where(func.lower(Event.city) == city.lower())
        total = (
            await self.db.execute(select(func.count()).select_from(stmt.subquery()))
        ).scalar_one()
        order = Event.starts_at.asc() if when != "past" else Event.starts_at.desc()
        rows = (
            await self.db.execute(
                stmt.options(selectinload(Event.translations))
                .order_by(order)
                .offset(params.offset)
                .limit(params.page_size)
            )
        ).scalars().all()
        items = [item for event in rows if (item := self._list_item(event, lang))]
        return Page.of(items, total, params)

    async def timeline(self, lang: str) -> list[EventListItem]:
        rows = (
            await self.db.execute(
                select(Event)
                .where(
                    published_filter(Event.status, Event.published_at),
                    Event.show_in_timeline.is_(True),
                )
                .options(selectinload(Event.translations))
                .order_by(Event.starts_at.asc())
            )
        ).scalars().all()
        return [item for event in rows if (item := self._list_item(event, lang))]

    async def get_public(self, slug: str, lang: str) -> EventOut:
        event = (
            await self.db.execute(
                select(Event)
                .where(Event.slug == slug, published_filter(Event.status, Event.published_at))
                .options(selectinload(Event.translations))
            )
        ).scalar_one_or_none()
        if event is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Événement introuvable", "code": "event_not_found"},
            )
        return await self._to_out(event, lang)

    async def calendar_ics(self, slug: str, lang: str) -> str:
        event = await self.get_public(slug, lang)
        start = _ics_dt(event.starts_at)
        end = _ics_dt(event.ends_at or event.starts_at)
        location = ", ".join(part for part in (event.venue, event.city) if part)
        description = event.description or event.summary or ""
        url = event.registration_url or event.online_url or ""
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//ourtdev//events//FR",
            "BEGIN:VEVENT",
            f"UID:{event.id}@ourtdev.com",
            f"DTSTAMP:{_ics_dt(now_utc())}",
            f"DTSTART:{start}",
            f"DTEND:{end}",
            f"SUMMARY:{_ics_text(event.title)}",
            f"DESCRIPTION:{_ics_text(description)}",
            f"LOCATION:{_ics_text(location)}",
        ]
        if url:
            lines.append(f"URL:{url}")
        lines.extend(["END:VEVENT", "END:VCALENDAR", ""])
        return "\r\n".join(lines)

    async def register(self, slug: str, body: RegisterRequest, auth: AuthContext) -> None:
        event = (
            await self.db.execute(
                select(Event).where(
                    Event.slug == slug, published_filter(Event.status, Event.published_at)
                )
            )
        ).scalar_one_or_none()
        if event is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Événement introuvable", "code": "event_not_found"},
            )
        if event.ends_at is not None and event.ends_at < now_utc():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "Inscriptions closes", "code": "registration_closed"},
            )
        existing = (
            await self.db.execute(
                select(EventParticipant).where(
                    EventParticipant.event_id == event.id,
                    EventParticipant.user_id == auth.user.id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"detail": "Déjà inscrit", "code": "already_registered"},
            )
        self.db.add(
            EventParticipant(event_id=event.id, user_id=auth.user.id, role=body.role)
        )
        await log_activity(
            self.db,
            actor_id=auth.user.id,
            action="register",
            entity_type="event",
            entity_id=str(event.id),
        )
        await self.db.commit()

    async def create(self, body: EventCreate, auth: AuthContext, lang: str) -> EventOut:
        self._assert_writer(auth)
        if body.ends_at is not None and body.ends_at < body.starts_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "ends_at avant starts_at", "code": "invalid_dates"},
            )
        taken = (
            await self.db.execute(select(Event.id).where(Event.slug == body.slug))
        ).scalar_one_or_none()
        if taken is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"detail": "Slug déjà utilisé", "code": "slug_taken"},
            )
        community_id = self._scoped_community(auth, body.community_id)
        await self._community_exists(community_id)
        await self._edition_exists(body.edition_year)
        event_status = ContentStatus(body.status)
        published_at = body.published_at
        show_stats = body.show_stats
        participants_count = body.participants_count
        sessions_count = body.sessions_count
        if not self._manages(auth):
            if event_status == ContentStatus.published:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"detail": "Publication réservée aux éditeurs", "code": "forbidden"},
                )
            show_stats = False
            participants_count = None
            sessions_count = None
        event = Event(
            slug=body.slug,
            type=EventType(body.type),
            format=EventFormat(body.format),
            starts_at=body.starts_at,
            ends_at=body.ends_at,
            timezone=body.timezone,
            venue=body.venue,
            city=body.city,
            country_code=body.country_code.upper() if body.country_code else None,
            online_url=body.online_url,
            registration_url=body.registration_url,
            replay_url=body.replay_url,
            cover_media_id=body.cover_media_id,
            community_id=community_id,
            edition_year=body.edition_year,
            show_in_timeline=body.show_in_timeline,
            participants_count=participants_count,
            sessions_count=sessions_count,
            show_stats=show_stats,
            status=event_status,
            published_at=published_at,
            created_by=auth.user.id,
            updated_by=auth.user.id,
        )
        self.db.add(event)
        await self.db.flush()
        await self._replace_translations(event.id, body.translations)
        if event.status == ContentStatus.published and event.published_at is not None:
            await self._ensure_resource_folder(event, auth.user.id)
        await log_activity(
            self.db,
            actor_id=auth.user.id,
            action="create",
            entity_type="event",
            entity_id=str(event.id),
        )
        await self.db.commit()
        saved_id = event.id
        self.db.expire_all()
        return await self._to_out(await self._get(saved_id), lang)

    async def update(self, event_id: uuid.UUID, body: EventUpdate, auth: AuthContext, lang: str) -> EventOut:
        self._assert_writer(auth)
        event = await self._get(event_id)
        self._assert_can_edit(auth, event)
        if not self._manages(auth) and body.status == "published":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"detail": "Publication réservée aux éditeurs", "code": "forbidden"},
            )
        if body.community_id is not None:
            community_id = self._scoped_community(auth, body.community_id)
            await self._community_exists(community_id)
            event.community_id = community_id
        if body.edition_year is not None:
            await self._edition_exists(body.edition_year)
            event.edition_year = body.edition_year
        for field in (
            "venue",
            "city",
            "online_url",
            "registration_url",
            "replay_url",
            "cover_media_id",
            "timezone",
            "starts_at",
            "ends_at",
            "show_in_timeline",
        ):
            value = getattr(body, field)
            if value is not None:
                setattr(event, field, value)
        if body.type is not None:
            event.type = EventType(body.type)
        if body.format is not None:
            event.format = EventFormat(body.format)
        if body.country_code is not None:
            event.country_code = body.country_code.upper()
        if self._manages(auth):
            if body.show_stats is not None:
                event.show_stats = body.show_stats
            if body.participants_count is not None:
                event.participants_count = body.participants_count
            if body.sessions_count is not None:
                event.sessions_count = body.sessions_count
            if body.status is not None:
                event.status = ContentStatus(body.status)
            if body.published_at is not None:
                event.published_at = body.published_at
        if event.ends_at is not None and event.ends_at < event.starts_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "ends_at avant starts_at", "code": "invalid_dates"},
            )
        if body.translations is not None:
            await self._replace_translations(event.id, body.translations)
        event.updated_by = auth.user.id
        if event.status == ContentStatus.published and event.published_at is not None:
            await self._ensure_resource_folder(event, auth.user.id)
        await log_activity(
            self.db,
            actor_id=auth.user.id,
            action="update",
            entity_type="event",
            entity_id=str(event.id),
        )
        await self.db.commit()
        saved_id = event.id
        self.db.expire_all()
        return await self._to_out(await self._get(saved_id), lang)

    async def publish(self, event_id: uuid.UUID, auth: AuthContext, lang: str) -> EventOut:
        event = await self._get(event_id)
        event.status = ContentStatus.published
        event.published_at = event.published_at or now_utc()
        event.updated_by = auth.user.id
        await self._ensure_resource_folder(event, auth.user.id)
        await log_activity(
            self.db,
            actor_id=auth.user.id,
            action="publish",
            entity_type="event",
            entity_id=str(event.id),
        )
        await self.db.commit()
        saved_id = event.id
        self.db.expire_all()
        return await self._to_out(await self._get(saved_id), lang)

    async def create_speaker(self, body: SpeakerCreate, auth: AuthContext) -> uuid.UUID:
        self._assert_writer(auth)
        speaker = Speaker(
            full_name=body.full_name,
            organization=body.organization,
            linkedin_url=body.linkedin_url,
            github_url=body.github_url,
            website_url=body.website_url,
            user_id=body.user_id,
        )
        self.db.add(speaker)
        await self.db.flush()
        for tr in body.translations:
            self.db.add(
                SpeakerTranslation(
                    speaker_id=speaker.id,
                    language_code=tr.language_code,
                    job_title=tr.job_title,
                    bio=tr.bio,
                )
            )
        await log_activity(
            self.db,
            actor_id=auth.user.id,
            action="create",
            entity_type="speaker",
            entity_id=str(speaker.id),
        )
        await self.db.commit()
        return speaker.id

    async def attach_speaker(
        self, event_id: uuid.UUID, body: EventSpeakerAttach, auth: AuthContext, lang: str
    ) -> EventOut:
        self._assert_writer(auth)
        event = await self._get(event_id)
        self._assert_can_edit(auth, event)
        speaker = (
            await self.db.execute(select(Speaker).where(Speaker.id == body.speaker_id))
        ).scalar_one_or_none()
        if speaker is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Intervenant introuvable", "code": "speaker_not_found"},
            )
        link = (
            await self.db.execute(
                select(EventSpeaker).where(
                    EventSpeaker.event_id == event.id, EventSpeaker.speaker_id == speaker.id
                )
            )
        ).scalar_one_or_none()
        if link is None:
            self.db.add(
                EventSpeaker(
                    event_id=event.id,
                    speaker_id=speaker.id,
                    role=body.role,
                    position=body.position,
                )
            )
        else:
            link.role = body.role
            link.position = body.position
        await self.db.commit()
        saved_id = event.id
        self.db.expire_all()
        return await self._to_out(await self._get(saved_id), lang)

    async def add_media(
        self, event_id: uuid.UUID, body: EventMediaCreate, auth: AuthContext, lang: str
    ) -> EventOut:
        self._assert_writer(auth)
        event = await self._get(event_id)
        self._assert_can_edit(auth, event)
        if body.media_id is None and not body.url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "media_id ou url requis", "code": "media_required"},
            )
        self.db.add(
            EventMedia(
                event_id=event.id,
                kind=body.kind,
                media_id=body.media_id,
                url=body.url,
                position=body.position,
            )
        )
        await self.db.commit()
        saved_id = event.id
        self.db.expire_all()
        return await self._to_out(await self._get(saved_id), lang)

    async def attach_partner(
        self, event_id: uuid.UUID, body: EventPartnerAttach, auth: AuthContext, lang: str
    ) -> EventOut:
        self._assert_writer(auth)
        event = await self._get(event_id)
        self._assert_can_edit(auth, event)
        partner = (
            await self.db.execute(select(Partner).where(Partner.id == body.partner_id))
        ).scalar_one_or_none()
        if partner is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Partenaire introuvable", "code": "partner_not_found"},
            )
        exists = (
            await self.db.execute(
                select(EventPartner).where(
                    EventPartner.event_id == event.id, EventPartner.partner_id == partner.id
                )
            )
        ).scalar_one_or_none()
        if exists is None:
            self.db.add(EventPartner(event_id=event.id, partner_id=partner.id))
        await self.db.commit()
        saved_id = event.id
        self.db.expire_all()
        return await self._to_out(await self._get(saved_id), lang)


def _ics_dt(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _ics_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )
