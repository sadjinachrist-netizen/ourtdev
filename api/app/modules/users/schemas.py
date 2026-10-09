"""Schémas Pydantic — users / settings."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class RoleOut(BaseModel):
    code: str
    label: str
    community_id: int | None = None


class MeResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    status: str
    email_verified_at: datetime | None
    preferred_language: str | None
    roles: list[RoleOut]
    permissions: list[str]


class SiteSettingOut(BaseModel):
    key: str
    value: Any
    description: str | None = None


class SiteSettingUpdate(BaseModel):
    value: Any
    description: str | None = Field(default=None)


class UsersStatus(BaseModel):
    module: str = "users"
    status: str = "ready"
