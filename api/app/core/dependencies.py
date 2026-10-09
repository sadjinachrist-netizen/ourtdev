from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Annotated, Callable

from fastapi import Depends, Header, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.rbac import get_user_permission_codes, get_user_roles, load_user
from app.core.security import decode_token
from app.modules.users.models import User, UserRole, UserStatus
from app.shared.i18n import resolve_language

DbSession = Annotated[AsyncSession, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    user: User
    permissions: set[str] = field(default_factory=set)
    roles: list[UserRole] = field(default_factory=list)

    @property
    def community_ids(self) -> list[int]:
        return [r.community_id for r in self.roles if r.community_id is not None]

    def has_permission(self, code: str) -> bool:
        return code in self.permissions


def get_language(
    accept_language: Annotated[str | None, Header(alias="Accept-Language")] = None,
    lang: Annotated[str | None, Query(description="fr | en")] = None,
) -> str:
    settings = get_settings()
    return resolve_language(
        query_lang=lang,
        accept_language=accept_language,
        default=settings.default_language,
    )


Language = Annotated[str, Depends(get_language)]


async def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Authentification requise", "code": "unauthorized"},
        )
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        user_id = uuid.UUID(str(payload["sub"]))
    except (ValueError, KeyError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Jeton invalide", "code": "invalid_token"},
        ) from None

    user = await load_user(db, user_id)
    if user is None or user.status in {UserStatus.suspended, UserStatus.deleted}:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Compte indisponible", "code": "user_unavailable"},
        )

    permissions = await get_user_permission_codes(db, user.id)
    roles = await get_user_roles(db, user.id)
    return AuthContext(user=user, permissions=permissions, roles=roles)


CurrentAuth = Annotated[AuthContext, Depends(get_current_user)]


def require_permission(code: str) -> Callable:
    async def _dependency(auth: CurrentAuth) -> AuthContext:
        if not auth.has_permission(code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"detail": f"Permission requise: {code}", "code": "forbidden"},
            )
        return auth

    return _dependency
