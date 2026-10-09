"""Schémas Pydantic — media."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class MediaOut(BaseModel):
    id: uuid.UUID
    storage_key: str
    url: str
    original_name: str | None
    mime_type: str
    size_bytes: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MediaStatus(BaseModel):
    module: str = "media"
    status: str = "ready"


class MediaUploadMeta(BaseModel):
    alt_text: str | None = Field(default=None)
    language_code: str = "fr"
