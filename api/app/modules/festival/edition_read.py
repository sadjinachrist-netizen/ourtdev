"""Lecture publique des éditions."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.festival.edition_common import to_edition_out
from app.modules.festival.models import FestivalEdition
from app.modules.festival.redirects import record_hit, upsert_redirect
from app.modules.festival.schemas import EditionOut, FestivalPage
from app.shared.publishing import published_filter


async def list_public(db: AsyncSession, lang: str) -> FestivalPage:
    rows = (
        await db.execute(
            select(FestivalEdition)
            .where(published_filter(FestivalEdition.status, FestivalEdition.published_at))
            .options(selectinload(FestivalEdition.translations))
            .order_by(FestivalEdition.year.desc())
        )
    ).scalars().all()
    editions = [await to_edition_out(db, row, lang) for row in rows]
    current = next((item for item in editions if item.is_current), None)
    archive = [item for item in editions if current is None or item.year != current.year]
    return FestivalPage(current=current, archive=archive)


async def get_current(db: AsyncSession, lang: str) -> EditionOut:
    edition = (
        await db.execute(
            select(FestivalEdition)
            .where(
                FestivalEdition.is_current.is_(True),
                published_filter(FestivalEdition.status, FestivalEdition.published_at),
            )
            .options(selectinload(FestivalEdition.translations))
        )
    ).scalar_one_or_none()
    if edition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Aucune édition en cours", "code": "no_current_edition"},
        )
    return await to_edition_out(db, edition, lang)


async def get_public(db: AsyncSession, year: int, lang: str) -> EditionOut:
    edition = (
        await db.execute(
            select(FestivalEdition)
            .where(
                FestivalEdition.year == year,
                published_filter(FestivalEdition.status, FestivalEdition.published_at),
            )
            .options(selectinload(FestivalEdition.translations))
        )
    ).scalar_one_or_none()
    if edition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Édition introuvable", "code": "edition_not_found"},
        )
    return await to_edition_out(db, edition, lang)


async def go(db: AsyncSession, year: int) -> tuple[str, int]:
    edition = await get_public(db, year, "fr")
    if not edition.target_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Lien d'édition absent", "code": "target_missing"},
        )
    source = f"/festival/{year}"
    await upsert_redirect(db, source, edition.target_url)
    await db.flush()
    code = await record_hit(db, source)
    await db.commit()
    return edition.target_url, code
