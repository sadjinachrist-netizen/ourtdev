"""Chargement et sérialisation d'une édition."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.contents.models import KeyFigure
from app.modules.festival.models import FestivalEdition, FestivalEditionTranslation
from app.modules.festival.schemas import EditionOut, FigureOut
from app.shared.i18n import pick_translation


async def clear_current(db: AsyncSession, except_year: int | None = None) -> None:
    stmt = update(FestivalEdition).where(FestivalEdition.is_current.is_(True))
    if except_year is not None:
        stmt = stmt.where(FestivalEdition.year != except_year)
    await db.execute(stmt.values(is_current=False))
    await db.flush()


async def save_translations(db: AsyncSession, year: int, items: list) -> None:
    rows = (
        await db.execute(
            select(FestivalEditionTranslation).where(FestivalEditionTranslation.edition_year == year)
        )
    ).scalars().all()
    existing = {row.language_code: row for row in rows}
    for tr in items:
        current = existing.get(tr.language_code)
        if current is None:
            db.add(
                FestivalEditionTranslation(
                    edition_year=year,
                    language_code=tr.language_code,
                    theme=tr.theme,
                    summary=tr.summary,
                    description=tr.description,
                )
            )
        else:
            current.theme = tr.theme
            current.summary = tr.summary
            current.description = tr.description


async def figures_for(db: AsyncSession, year: int, lang: str) -> list[FigureOut]:
    rows = (
        await db.execute(
            select(KeyFigure)
            .where(KeyFigure.edition_year == year, KeyFigure.is_active.is_(True))
            .options(selectinload(KeyFigure.translations))
            .order_by(KeyFigure.position, KeyFigure.code)
        )
    ).scalars().all()
    result: list[FigureOut] = []
    for fig in rows:
        tr = pick_translation(fig.translations, lang)
        if tr is None:
            continue
        result.append(
            FigureOut(
                id=fig.id,
                code=fig.code,
                value=fig.value,
                suffix=fig.suffix,
                language=tr.language_code,
                label=tr.label,
                position=fig.position,
            )
        )
    return result


async def load_edition(db: AsyncSession, year: int) -> FestivalEdition:
    edition = (
        await db.execute(
            select(FestivalEdition)
            .where(FestivalEdition.year == year)
            .options(selectinload(FestivalEdition.translations))
        )
    ).scalar_one_or_none()
    if edition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Édition introuvable", "code": "edition_not_found"},
        )
    return edition


async def to_edition_out(db: AsyncSession, edition: FestivalEdition, lang: str) -> EditionOut:
    tr = pick_translation(edition.translations, lang)
    if tr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Traduction manquante", "code": "translation_missing"},
        )
    return EditionOut(
        year=edition.year,
        starts_on=edition.starts_on,
        ends_on=edition.ends_on,
        city=edition.city,
        venue=edition.venue,
        target_url=edition.target_url,
        is_current=edition.is_current,
        status=edition.status.value,
        published_at=edition.published_at,
        language=tr.language_code,
        theme=tr.theme,
        summary=tr.summary,
        description=tr.description,
        figures=await figures_for(db, edition.year, lang),
    )


def check_dates(starts_on, ends_on) -> None:
    if starts_on is not None and ends_on is not None and ends_on < starts_on:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "ends_on avant starts_on", "code": "invalid_dates"},
        )
