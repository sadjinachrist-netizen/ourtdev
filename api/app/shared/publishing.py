"""Helpers de publication planifiée."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_

from app.modules.contents.models import ContentStatus


def now_utc() -> datetime:
    return datetime.now(UTC)


def is_publicly_visible(status: ContentStatus | str, published_at: datetime | None) -> bool:
    status_val = status.value if isinstance(status, ContentStatus) else status
    if status_val != ContentStatus.published.value:
        return False
    if published_at is None:
        return False
    pub = published_at if published_at.tzinfo else published_at.replace(tzinfo=UTC)
    return pub <= now_utc()


def published_filter(status_col, published_at_col):
    """Clause SQLAlchemy : publié et date passée."""
    return and_(
        status_col == ContentStatus.published,
        published_at_col.is_not(None),
        published_at_col <= now_utc(),
    )
