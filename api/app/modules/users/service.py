"""Logique métier — users / settings."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext
from app.modules.users.models import SiteSetting
from app.modules.users.schemas import MeResponse, RoleOut, SiteSettingOut
from app.shared.activity import log_activity

PUBLIC_SETTING_KEYS = frozenset({"site_name", "default_language", "social_links"})


class UsersService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def me(self, auth: AuthContext) -> MeResponse:
        roles = [
            RoleOut(
                code=ur.role.code,
                label=ur.role.label,
                community_id=ur.community_id,
            )
            for ur in auth.roles
        ]
        return MeResponse(
            id=auth.user.id,
            email=auth.user.email,
            status=auth.user.status.value if hasattr(auth.user.status, "value") else str(auth.user.status),
            email_verified_at=auth.user.email_verified_at,
            preferred_language=auth.user.preferred_language,
            roles=roles,
            permissions=sorted(auth.permissions),
        )

    async def list_settings(self, *, include_all: bool) -> list[SiteSettingOut]:
        result = await self.db.execute(select(SiteSetting))
        rows = result.scalars().all()
        out: list[SiteSettingOut] = []
        for row in rows:
            if not include_all and row.key not in PUBLIC_SETTING_KEYS:
                continue
            out.append(
                SiteSettingOut(key=row.key, value=row.value, description=row.description)
            )
        return out

    async def update_setting(
        self,
        *,
        key: str,
        value: Any,
        description: str | None,
        auth: AuthContext,
    ) -> SiteSettingOut:
        result = await self.db.execute(select(SiteSetting).where(SiteSetting.key == key))
        row = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Paramètre introuvable", "code": "setting_not_found"},
            )
        row.value = value
        if description is not None:
            row.description = description
        row.updated_by = auth.user.id
        await log_activity(
            self.db,
            actor_id=auth.user.id,
            action="update",
            entity_type="site_setting",
            entity_id=key,
            changes={"value": value},
        )
        await self.db.commit()
        await self.db.refresh(row)
        return SiteSettingOut(key=row.key, value=row.value, description=row.description)
