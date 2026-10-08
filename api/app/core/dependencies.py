from typing import Annotated

from fastapi import Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.shared.i18n import resolve_language

DbSession = Annotated[AsyncSession, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_language(
    accept_language: Annotated[str | None, Header(alias="Accept-Language")] = None,
    lang: Annotated[str | None, Query(description="fr | en")] = None,
) -> str:
    """Langue effective : query `lang` > Accept-Language > défaut fr."""
    settings = get_settings()
    return resolve_language(
        query_lang=lang,
        accept_language=accept_language,
        default=settings.default_language,
    )


Language = Annotated[str, Depends(get_language)]
