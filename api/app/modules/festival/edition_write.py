"""Création et modification des éditions."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext
from app.modules.contents.models import ContentStatus, KeyFigure, KeyFigureTranslation
from app.modules.festival.edition_common import (
    check_dates,
    clear_current,
    load_edition,
    save_translations,
    to_edition_out,
)
from app.modules.festival.models import FestivalEdition
from app.modules.festival.redirects import sync_edition_redirect
from app.modules.festival.schemas import EditionCreate, EditionOut, EditionUpdate, FigureCreate
from app.shared.activity import log_activity
from app.shared.publishing import now_utc


async def create_edition(db: AsyncSession, body: EditionCreate, auth: AuthContext, lang: str) -> EditionOut:
    check_dates(body.starts_on, body.ends_on)
    taken = (
        await db.execute(select(FestivalEdition.year).where(FestivalEdition.year == body.year))
    ).scalar_one_or_none()
    if taken is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": "Édition déjà existante", "code": "edition_exists"},
        )
    if body.is_current:
        await clear_current(db)
    edition = FestivalEdition(
        year=body.year,
        starts_on=body.starts_on,
        ends_on=body.ends_on,
        city=body.city,
        venue=body.venue,
        target_url=body.target_url,
        is_current=body.is_current,
        status=ContentStatus(body.status),
        published_at=body.published_at,
    )
    db.add(edition)
    await db.flush()
    await save_translations(db, edition.year, body.translations)
    if edition.target_url:
        await sync_edition_redirect(db, edition, None)
    await log_activity(
        db,
        actor_id=auth.user.id,
        action="create",
        entity_type="festival_edition",
        entity_id=str(edition.year),
    )
    await db.commit()
    db.expire_all()
    return await to_edition_out(db, await load_edition(db, body.year), lang)


async def update_edition(db: AsyncSession, year: int, body: EditionUpdate, auth: AuthContext, lang: str) -> EditionOut:
    edition = await load_edition(db, year)
    previous_url = edition.target_url
    if body.is_current:
        await clear_current(db, except_year=year)
        edition.is_current = True
    elif body.is_current is False:
        edition.is_current = False
    for field in ("starts_on", "ends_on", "city", "venue", "target_url", "published_at"):
        value = getattr(body, field)
        if value is not None:
            setattr(edition, field, value)
    if body.status is not None:
        edition.status = ContentStatus(body.status)
    check_dates(edition.starts_on, edition.ends_on)
    if body.translations is not None:
        await save_translations(db, year, body.translations)
    if edition.target_url and edition.target_url != previous_url:
        await sync_edition_redirect(db, edition, previous_url)
    await log_activity(
        db, actor_id=auth.user.id, action="update", entity_type="festival_edition", entity_id=str(year)
    )
    await db.commit()
    db.expire_all()
    return await to_edition_out(db, await load_edition(db, year), lang)


async def publish_edition(db: AsyncSession, year: int, auth: AuthContext, lang: str) -> EditionOut:
    edition = await load_edition(db, year)
    edition.status = ContentStatus.published
    edition.published_at = edition.published_at or now_utc()
    if edition.target_url:
        await sync_edition_redirect(db, edition, None)
    await log_activity(
        db, actor_id=auth.user.id, action="publish", entity_type="festival_edition", entity_id=str(year)
    )
    await db.commit()
    db.expire_all()
    return await to_edition_out(db, await load_edition(db, year), lang)


async def add_figure(db: AsyncSession, year: int, body: FigureCreate, auth: AuthContext, lang: str) -> EditionOut:
    await load_edition(db, year)
    exists = (
        await db.execute(
            select(KeyFigure.id).where(KeyFigure.code == body.code, KeyFigure.edition_year == year)
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": "Chiffre déjà existant", "code": "figure_exists"},
        )
    figure = KeyFigure(
        code=body.code,
        value=body.value,
        suffix=body.suffix,
        edition_year=year,
        show_on_home=False,
        position=body.position,
        is_active=True,
        updated_by=auth.user.id,
    )
    db.add(figure)
    await db.flush()
    db.add(KeyFigureTranslation(key_figure_id=figure.id, language_code="fr", label=body.label_fr))
    if body.label_en:
        db.add(KeyFigureTranslation(key_figure_id=figure.id, language_code="en", label=body.label_en))
    await log_activity(
        db,
        actor_id=auth.user.id,
        action="create",
        entity_type="key_figure",
        entity_id=str(figure.id),
        changes={"edition_year": year, "code": body.code},
    )
    await db.commit()
    db.expire_all()
    return await to_edition_out(db, await load_edition(db, year), lang)
