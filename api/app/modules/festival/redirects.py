"""Redirections 301 et compteur de passages."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext
from app.modules.festival.models import FestivalEdition
from app.modules.users.models import Redirect
from app.modules.festival.schemas import RedirectCreate, RedirectOut, RedirectUpdate
from app.shared.activity import log_activity


def _out(row: Redirect) -> RedirectOut:
    return RedirectOut(
        id=row.id,
        source_path=row.source_path,
        target_url=row.target_url,
        status_code=row.status_code,
        is_active=row.is_active,
        hit_count=row.hit_count,
    )


async def upsert_redirect(db: AsyncSession, source_path: str, target_url: str) -> None:
    if not source_path.startswith("/"):
        return
    row = (await db.execute(select(Redirect).where(Redirect.source_path == source_path))).scalar_one_or_none()
    if row is None:
        db.add(Redirect(source_path=source_path, target_url=target_url, status_code=301, is_active=True))
    else:
        row.target_url = target_url
        row.status_code = 301
        row.is_active = True


async def sync_edition_redirect(db: AsyncSession, edition: FestivalEdition, previous_url: str | None) -> None:
    if not edition.target_url:
        return
    source = f"/festival/{edition.year}"
    if (
        previous_url
        and previous_url != edition.target_url
        and previous_url.startswith("/")
        and previous_url != source
    ):
        await upsert_redirect(db, previous_url, edition.target_url)
    await upsert_redirect(db, source, edition.target_url)


async def record_hit(db: AsyncSession, source_path: str) -> int:
    row = (
        await db.execute(
            select(Redirect).where(Redirect.source_path == source_path, Redirect.is_active.is_(True))
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Redirection introuvable", "code": "redirect_not_found"},
        )
    row.hit_count += 1
    row.updated_at = datetime.now(UTC)
    return row.status_code


async def resolve(db: AsyncSession, source_path: str) -> tuple[str, int]:
    if not source_path.startswith("/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Le chemin doit commencer par /", "code": "invalid_path"},
        )
    row = (
        await db.execute(
            select(Redirect).where(Redirect.source_path == source_path, Redirect.is_active.is_(True))
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Redirection introuvable", "code": "redirect_not_found"},
        )
    target = row.target_url
    code = await record_hit(db, source_path)
    await db.commit()
    return target, code


async def list_redirects(db: AsyncSession) -> list[RedirectOut]:
    rows = (await db.execute(select(Redirect).order_by(Redirect.source_path))).scalars().all()
    return [_out(row) for row in rows]


async def create_redirect(db: AsyncSession, body: RedirectCreate, auth: AuthContext) -> RedirectOut:
    taken = (
        await db.execute(select(Redirect).where(Redirect.source_path == body.source_path))
    ).scalar_one_or_none()
    if taken is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": "Chemin déjà redirigé", "code": "redirect_exists"},
        )
    row = Redirect(
        source_path=body.source_path,
        target_url=body.target_url,
        status_code=body.status_code,
        is_active=body.is_active,
    )
    db.add(row)
    await log_activity(db, actor_id=auth.user.id, action="create", entity_type="redirect", entity_id=body.source_path)
    await db.commit()
    await db.refresh(row)
    return _out(row)


async def update_redirect(db: AsyncSession, redirect_id: int, body: RedirectUpdate, auth: AuthContext) -> RedirectOut:
    row = (await db.execute(select(Redirect).where(Redirect.id == redirect_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Redirection introuvable", "code": "redirect_not_found"},
        )
    if body.target_url is not None:
        row.target_url = body.target_url
    if body.status_code is not None:
        row.status_code = body.status_code
    if body.is_active is not None:
        row.is_active = body.is_active
    await log_activity(
        db, actor_id=auth.user.id, action="update", entity_type="redirect", entity_id=str(redirect_id)
    )
    await db.commit()
    return _out(row)
