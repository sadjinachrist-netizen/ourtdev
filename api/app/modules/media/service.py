"""Logique métier — médiathèque (stockage local)."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.dependencies import AuthContext
from app.modules.users.models import MediaFile, MediaFileTranslation
from app.shared.activity import log_activity

ALLOWED_PREFIXES = ("image/", "application/pdf", "application/vnd", "text/", "video/")


class MediaService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.root = Path(settings.media_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    async def upload(
        self,
        *,
        file: UploadFile,
        auth: AuthContext,
        alt_text: str | None = None,
        language_code: str = "fr",
    ) -> MediaFile:
        if not file.content_type or not any(
            file.content_type.startswith(p) for p in ALLOWED_PREFIXES
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "Type de fichier non autorisé", "code": "invalid_mime"},
            )

        media_id = uuid.uuid4()
        safe_name = Path(file.filename or "file").name.replace("..", "_")
        storage_key = f"{media_id}/{safe_name}"
        dest = self.root / str(media_id)
        dest.mkdir(parents=True, exist_ok=True)
        path = dest / safe_name

        data = await file.read()
        path.write_bytes(data)

        url = f"{self.settings.media_base_url.rstrip('/')}/{storage_key}"
        media = MediaFile(
            id=media_id,
            storage_key=storage_key,
            url=url,
            original_name=file.filename,
            mime_type=file.content_type,
            size_bytes=len(data),
            uploaded_by=auth.user.id,
        )
        self.db.add(media)
        if alt_text:
            self.db.add(
                MediaFileTranslation(
                    media_id=media_id,
                    language_code=language_code,
                    alt_text=alt_text,
                )
            )
        await log_activity(
            self.db,
            actor_id=auth.user.id,
            action="upload",
            entity_type="media",
            entity_id=str(media_id),
        )
        await self.db.commit()
        await self.db.refresh(media)
        return media

    async def get(self, media_id: uuid.UUID) -> MediaFile:
        result = await self.db.execute(select(MediaFile).where(MediaFile.id == media_id))
        media = result.scalar_one_or_none()
        if media is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Média introuvable", "code": "media_not_found"},
            )
        return media
