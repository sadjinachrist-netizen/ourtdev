from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import ActivityLog


async def log_activity(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: str,
    changes: dict[str, Any] | None = None,
) -> ActivityLog:
    entry = ActivityLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        changes=changes,
    )
    db.add(entry)
    await db.flush()
    return entry
