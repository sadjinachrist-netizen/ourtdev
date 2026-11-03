"""Annonces du bandeau festival."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import AuthContext
from app.modules.festival.edition_common import load_edition
from app.modules.festival.models import Announcement, AnnouncementTranslation, FestivalEdition
from app.modules.festival.schemas import AnnouncementCreate, AnnouncementOut, AnnouncementUpdate
from app.shared.activity import log_activity
from app.shared.i18n import pick_translation
from app.shared.publishing import now_utc, published_filter


def to_announcement(row: Announcement, lang: str) -> AnnouncementOut | None:
    tr = pick_translation(row.translations, lang)
    if tr is None:
        return None
    return AnnouncementOut(
        id=row.id,
        edition_year=row.edition_year,
        kind=row.kind,
        message=tr.message,
        cta_label=tr.cta_label,
        cta_url=row.cta_url,
        language=tr.language_code,
        position=row.position,
    )


async def active_announcements(db: AsyncSession, lang: str) -> list[AnnouncementOut]:
    now = now_utc()
    rows = (
        await db.execute(
            select(Announcement)
            .where(
                Announcement.is_active.is_(True),
                Announcement.starts_at <= now,
                or_(Announcement.ends_at.is_(None), Announcement.ends_at > now),
            )
            .options(selectinload(Announcement.translations))
            .order_by(Announcement.position, Announcement.starts_at.desc())
        )
    ).scalars().all()
    visible: list[AnnouncementOut] = []
    for row in rows:
        if row.edition_year is not None:
            published = (
                await db.execute(
                    select(FestivalEdition.year).where(
                        FestivalEdition.year == row.edition_year,
                        published_filter(FestivalEdition.status, FestivalEdition.published_at),
                    )
                )
            ).scalar_one_or_none()
            if published is None:
                continue
        item = to_announcement(row, lang)
        if item is not None:
            visible.append(item)
    return visible


async def _reload(db: AsyncSession, announcement_id: uuid.UUID, lang: str) -> AnnouncementOut:
    loaded = (
        await db.execute(
            select(Announcement)
            .where(Announcement.id == announcement_id)
            .options(selectinload(Announcement.translations))
        )
    ).scalar_one()
    out = to_announcement(loaded, lang)
    if out is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Traduction manquante", "code": "translation_missing"},
        )
    return out


async def create_announcement(
    db: AsyncSession, body: AnnouncementCreate, auth: AuthContext, lang: str
) -> AnnouncementOut:
    if body.ends_at is not None and body.ends_at <= body.starts_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "ends_at doit être après starts_at", "code": "invalid_dates"},
        )
    if body.edition_year is not None:
        await load_edition(db, body.edition_year)
    row = Announcement(
        edition_year=body.edition_year,
        kind=body.kind,
        cta_url=body.cta_url,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        is_active=body.is_active,
        position=body.position,
        created_by=auth.user.id,
    )
    db.add(row)
    await db.flush()
    for tr in body.translations:
        db.add(
            AnnouncementTranslation(
                announcement_id=row.id,
                language_code=tr.language_code,
                message=tr.message,
                cta_label=tr.cta_label,
            )
        )
    saved_id = row.id
    await log_activity(
        db, actor_id=auth.user.id, action="create", entity_type="announcement", entity_id=str(saved_id)
    )
    await db.commit()
    db.expire_all()
    return await _reload(db, saved_id, lang)


async def update_announcement(
    db: AsyncSession, announcement_id: uuid.UUID, body: AnnouncementUpdate, auth: AuthContext, lang: str
) -> AnnouncementOut:
    row = (
        await db.execute(
            select(Announcement)
            .where(Announcement.id == announcement_id)
            .options(selectinload(Announcement.translations))
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Annonce introuvable", "code": "announcement_not_found"},
        )
    for field in ("kind", "cta_url", "starts_at", "ends_at", "is_active", "position"):
        value = getattr(body, field)
        if value is not None:
            setattr(row, field, value)
    if row.ends_at is not None and row.ends_at <= row.starts_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "ends_at doit être après starts_at", "code": "invalid_dates"},
        )
    if body.translations is not None:
        existing = {tr.language_code: tr for tr in row.translations}
        for tr in body.translations:
            current = existing.get(tr.language_code)
            if current is None:
                db.add(
                    AnnouncementTranslation(
                        announcement_id=row.id,
                        language_code=tr.language_code,
                        message=tr.message,
                        cta_label=tr.cta_label,
                    )
                )
            else:
                current.message = tr.message
                current.cta_label = tr.cta_label
    await log_activity(
        db,
        actor_id=auth.user.id,
        action="update",
        entity_type="announcement",
        entity_id=str(announcement_id),
    )
    await db.commit()
    db.expire_all()
    return await _reload(db, announcement_id, lang)
