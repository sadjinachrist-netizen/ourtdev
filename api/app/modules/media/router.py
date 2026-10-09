"""Routes FastAPI — media."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.core.dependencies import AppSettings, AuthContext, DbSession, require_permission
from app.modules.media.schemas import MediaOut, MediaStatus
from app.modules.media.service import MediaService

router = APIRouter(prefix="/media", tags=["media"])


@router.get("/status", response_model=MediaStatus, summary="Stub statut module media")
async def media_status() -> MediaStatus:
    return MediaStatus()


@router.post("", response_model=MediaOut, summary="Uploader un fichier")
async def upload_media(
    db: DbSession,
    settings: AppSettings,
    auth: Annotated[AuthContext, Depends(require_permission("media.manage"))],
    file: Annotated[UploadFile, File()],
    alt_text: Annotated[str | None, Form()] = None,
    language_code: Annotated[str, Form()] = "fr",
) -> MediaOut:
    media = await MediaService(db, settings).upload(
        file=file,
        auth=auth,
        alt_text=alt_text,
        language_code=language_code,
    )
    return MediaOut.model_validate(media)


@router.get("/{media_id}", response_model=MediaOut, summary="Métadonnées d'un média")
async def get_media(media_id: uuid.UUID, db: DbSession, settings: AppSettings) -> MediaOut:
    media = await MediaService(db, settings).get(media_id)
    return MediaOut.model_validate(media)
