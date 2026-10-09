"""Logique métier — authentification."""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
import pyotp
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.rbac import user_has_role
from app.core.security import (
    create_access_token,
    create_mfa_ticket,
    decrypt_secret,
    encrypt_secret,
    generate_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.modules.users.models import (
    MfaRecoveryCode,
    OAuthAccount,
    OneTimeToken,
    RefreshToken,
    Role,
    SiteSetting,
    User,
    UserMfa,
    UserRole,
    UserStatus,
)
from app.shared.activity import log_activity
from app.shared.email import send_email

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def _get_member_validation(self) -> str:
        result = await self.db.execute(
            select(SiteSetting).where(SiteSetting.key == "member_validation")
        )
        row = result.scalar_one_or_none()
        if row is None:
            return "email"
        value = row.value
        if isinstance(value, str):
            return value.strip('"')
        return str(value)

    async def _assign_role(self, user: User, role_code: str) -> None:
        role = (
            await self.db.execute(select(Role).where(Role.code == role_code))
        ).scalar_one()
        existing = (
            await self.db.execute(
                select(UserRole).where(
                    UserRole.user_id == user.id,
                    UserRole.role_id == role.id,
                    UserRole.community_id.is_(None),
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            self.db.add(UserRole(user_id=user.id, role_id=role.id))

    async def _create_one_time_token(self, user: User, purpose: str, hours: int = 24) -> str:
        raw = generate_token()
        self.db.add(
            OneTimeToken(
                user_id=user.id,
                purpose=purpose,
                token_hash=hash_token(raw),
                expires_at=datetime.now(UTC) + timedelta(hours=hours),
            )
        )
        return raw

    async def _issue_tokens(self, user: User, user_agent: str | None = None) -> dict[str, str]:
        access = create_access_token(str(user.id))
        raw_refresh = generate_token()
        self.db.add(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_token(raw_refresh),
                expires_at=datetime.now(UTC)
                + timedelta(days=self.settings.refresh_token_expire_days),
                user_agent=user_agent,
            )
        )
        user.last_login_at = datetime.now(UTC)
        await self.db.commit()
        return {
            "access_token": access,
            "refresh_token": raw_refresh,
            "token_type": "bearer",
        }

    async def register(
        self,
        *,
        email: str,
        password: str,
        preferred_language: str | None,
    ) -> User:
        existing = (
            await self.db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"detail": "Email déjà utilisé", "code": "email_taken"},
            )

        validation = await self._get_member_validation()
        user = User(
            email=email.lower(),
            password_hash=hash_password(password),
            status=UserStatus.pending,
            preferred_language=preferred_language or self.settings.default_language,
        )
        self.db.add(user)
        await self.db.flush()
        await self._assign_role(user, "member")

        if validation in {"email", "both"}:
            raw = await self._create_one_time_token(user, "verify_email")
            link = f"{self.settings.frontend_url}/verify-email?token={raw}"
            await send_email(
                to=user.email,
                subject="Vérifiez votre email — TDEV",
                body=f"Bonjour,\n\nConfirmez votre inscription : {link}\n",
            )

        await log_activity(
            self.db,
            actor_id=user.id,
            action="register",
            entity_type="user",
            entity_id=str(user.id),
        )
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def login(
        self,
        *,
        email: str,
        password: str,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        user = (
            await self.db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if user is None or not user.password_hash or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"detail": "Identifiants invalides", "code": "invalid_credentials"},
            )
        if user.status in {UserStatus.suspended, UserStatus.deleted}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"detail": "Compte indisponible", "code": "user_unavailable"},
            )

        is_admin = await user_has_role(self.db, user.id, "admin")
        mfa = (
            await self.db.execute(select(UserMfa).where(UserMfa.user_id == user.id))
        ).scalar_one_or_none()
        if is_admin and mfa is not None and mfa.enabled_at is not None:
            return {
                "mfa_required": True,
                "mfa_ticket": create_mfa_ticket(str(user.id)),
                "detail": "Double authentification requise",
            }

        return await self._issue_tokens(user, user_agent=user_agent)

    async def refresh(self, *, refresh_token: str, user_agent: str | None = None) -> dict[str, str]:
        token_hash = hash_token(refresh_token)
        row = (
            await self.db.execute(
                select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            )
        ).scalar_one_or_none()
        now = datetime.now(UTC)
        if (
            row is None
            or row.revoked_at is not None
            or row.expires_at.replace(tzinfo=UTC) < now
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"detail": "Refresh token invalide", "code": "invalid_refresh"},
            )

        row.revoked_at = now
        user = (
            await self.db.execute(select(User).where(User.id == row.user_id))
        ).scalar_one()
        return await self._issue_tokens(user, user_agent=user_agent)

    async def logout(self, *, refresh_token: str) -> None:
        token_hash = hash_token(refresh_token)
        row = (
            await self.db.execute(
                select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            )
        ).scalar_one_or_none()
        if row and row.revoked_at is None:
            row.revoked_at = datetime.now(UTC)
            await self.db.commit()

    async def verify_email(self, *, token: str) -> User:
        user = await self._consume_one_time_token(token, "verify_email")
        user.email_verified_at = datetime.now(UTC)
        validation = await self._get_member_validation()
        if validation == "email":
            user.status = UserStatus.active
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def forgot_password(self, *, email: str) -> None:
        user = (
            await self.db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        # Ne pas révéler si l'email existe
        if user is None:
            return
        raw = await self._create_one_time_token(user, "reset_password", hours=2)
        link = f"{self.settings.frontend_url}/reset-password?token={raw}"
        await send_email(
            to=user.email,
            subject="Réinitialisation du mot de passe — TDEV",
            body=f"Réinitialisez votre mot de passe : {link}\n",
        )
        await self.db.commit()

    async def reset_password(self, *, token: str, new_password: str) -> None:
        user = await self._consume_one_time_token(token, "reset_password")
        user.password_hash = hash_password(new_password)
        await self.db.commit()

    async def _consume_one_time_token(self, raw: str, purpose: str) -> User:
        token_hash = hash_token(raw)
        row = (
            await self.db.execute(
                select(OneTimeToken).where(OneTimeToken.token_hash == token_hash)
            )
        ).scalar_one_or_none()
        now = datetime.now(UTC)
        if (
            row is None
            or row.purpose != purpose
            or row.used_at is not None
            or row.expires_at.replace(tzinfo=UTC) < now
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "Jeton invalide ou expiré", "code": "invalid_token"},
            )
        row.used_at = now
        user = (
            await self.db.execute(select(User).where(User.id == row.user_id))
        ).scalar_one()
        return user

    def oauth_authorize_url(self, provider: str) -> str:
        if provider == "github":
            if not self.settings.github_client_id:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={"detail": "OAuth GitHub non configuré", "code": "oauth_not_configured"},
                )
            params = {
                "client_id": self.settings.github_client_id,
                "redirect_uri": self.settings.github_redirect_uri,
                "scope": "read:user user:email",
                "state": generate_token(16),
            }
            return f"https://github.com/login/oauth/authorize?{urlencode(params)}"
        if provider == "google":
            if not self.settings.google_client_id:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={"detail": "OAuth Google non configuré", "code": "oauth_not_configured"},
                )
            params = {
                "client_id": self.settings.google_client_id,
                "redirect_uri": self.settings.google_redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "access_type": "online",
                "state": generate_token(16),
            }
            return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Provider inconnu", "code": "invalid_provider"},
        )

    async def oauth_callback(
        self,
        *,
        provider: str,
        code: str,
        user_agent: str | None = None,
    ) -> dict[str, str]:
        if provider == "github":
            email, provider_user_id = await self._github_profile(code)
        elif provider == "google":
            email, provider_user_id = await self._google_profile(code)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "Provider inconnu", "code": "invalid_provider"},
            )

        account = (
            await self.db.execute(
                select(OAuthAccount).where(
                    OAuthAccount.provider == provider,
                    OAuthAccount.provider_user_id == provider_user_id,
                )
            )
        ).scalar_one_or_none()

        if account:
            user = (
                await self.db.execute(select(User).where(User.id == account.user_id))
            ).scalar_one()
        else:
            user = (
                await self.db.execute(select(User).where(User.email == email))
            ).scalar_one_or_none()
            if user is None:
                user = User(
                    email=email.lower(),
                    password_hash=None,
                    status=UserStatus.active,
                    email_verified_at=datetime.now(UTC),
                    preferred_language=self.settings.default_language,
                )
                self.db.add(user)
                await self.db.flush()
                await self._assign_role(user, "member")
            self.db.add(
                OAuthAccount(
                    user_id=user.id,
                    provider=provider,
                    provider_user_id=provider_user_id,
                )
            )
            await self.db.flush()

        return await self._issue_tokens(user, user_agent=user_agent)

    async def _github_profile(self, code: str) -> tuple[str, str]:
        async with httpx.AsyncClient() as client:
            token_res = await client.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": self.settings.github_client_id,
                    "client_secret": self.settings.github_client_secret,
                    "code": code,
                    "redirect_uri": self.settings.github_redirect_uri,
                },
            )
            token_res.raise_for_status()
            access = token_res.json().get("access_token")
            if not access:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"detail": "Code OAuth invalide", "code": "oauth_failed"},
                )
            user_res = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {access}", "Accept": "application/json"},
            )
            user_res.raise_for_status()
            data = user_res.json()
            email = data.get("email")
            if not email:
                emails_res = await client.get(
                    "https://api.github.com/user/emails",
                    headers={"Authorization": f"Bearer {access}", "Accept": "application/json"},
                )
                emails_res.raise_for_status()
                emails = emails_res.json()
                primary = next((e for e in emails if e.get("primary") and e.get("verified")), None)
                email = (primary or emails[0])["email"] if emails else None
            if not email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"detail": "Email GitHub indisponible", "code": "oauth_no_email"},
                )
            return email, str(data["id"])

    async def _google_profile(self, code: str) -> tuple[str, str]:
        async with httpx.AsyncClient() as client:
            token_res = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self.settings.google_client_id,
                    "client_secret": self.settings.google_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.settings.google_redirect_uri,
                },
            )
            token_res.raise_for_status()
            access = token_res.json().get("access_token")
            if not access:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"detail": "Code OAuth invalide", "code": "oauth_failed"},
                )
            user_res = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access}"},
            )
            user_res.raise_for_status()
            data = user_res.json()
            email = data.get("email")
            if not email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"detail": "Email Google indisponible", "code": "oauth_no_email"},
                )
            return email, str(data["id"])

    async def mfa_setup(self, user: User) -> dict[str, str]:
        secret = pyotp.random_base32()
        enc = encrypt_secret(secret)
        existing = (
            await self.db.execute(select(UserMfa).where(UserMfa.user_id == user.id))
        ).scalar_one_or_none()
        if existing is None:
            self.db.add(UserMfa(user_id=user.id, totp_secret_enc=enc))
        else:
            existing.totp_secret_enc = enc
            existing.enabled_at = None
        await self.db.commit()
        totp = pyotp.TOTP(secret)
        return {
            "secret": secret,
            "otpauth_url": totp.provisioning_uri(name=user.email, issuer_name="ourtdev"),
        }

    async def mfa_enable(self, user: User, code: str) -> list[str]:
        mfa = (
            await self.db.execute(select(UserMfa).where(UserMfa.user_id == user.id))
        ).scalar_one_or_none()
        if mfa is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "MFA non initialisé", "code": "mfa_not_setup"},
            )
        secret = decrypt_secret(mfa.totp_secret_enc)
        if not pyotp.TOTP(secret).verify(code, valid_window=1):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "Code MFA invalide", "code": "invalid_mfa_code"},
            )
        mfa.enabled_at = datetime.now(UTC)
        # Remplacer les recovery codes
        old = (
            await self.db.execute(select(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id))
        ).scalars().all()
        for row in old:
            await self.db.delete(row)  # SQLAlchemy 2 AsyncSession.delete
        plain_codes: list[str] = []
        for _ in range(8):
            code_plain = secrets.token_hex(4)
            plain_codes.append(code_plain)
            self.db.add(
                MfaRecoveryCode(user_id=user.id, code_hash=hash_token(code_plain))
            )
        await log_activity(
            self.db,
            actor_id=user.id,
            action="mfa_enable",
            entity_type="user",
            entity_id=str(user.id),
        )
        await self.db.commit()
        return plain_codes

    async def mfa_verify(
        self,
        *,
        mfa_ticket: str,
        code: str,
        user_agent: str | None = None,
    ) -> dict[str, str]:
        from app.core.security import decode_token
        import uuid

        try:
            payload = decode_token(mfa_ticket, expected_type="mfa")
            user_id = uuid.UUID(str(payload["sub"]))
        except (ValueError, KeyError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"detail": "Ticket MFA invalide", "code": "invalid_mfa_ticket"},
            ) from None

        user = (await self.db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"detail": "Utilisateur introuvable", "code": "user_not_found"},
            )

        mfa = (
            await self.db.execute(select(UserMfa).where(UserMfa.user_id == user.id))
        ).scalar_one_or_none()
        if mfa is None or mfa.enabled_at is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "MFA non activé", "code": "mfa_not_enabled"},
            )

        secret = decrypt_secret(mfa.totp_secret_enc)
        ok = pyotp.TOTP(secret).verify(code, valid_window=1)
        if not ok:
            # recovery code ?
            recovery = (
                await self.db.execute(
                    select(MfaRecoveryCode).where(
                        MfaRecoveryCode.user_id == user.id,
                        MfaRecoveryCode.code_hash == hash_token(code),
                        MfaRecoveryCode.used_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if recovery is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"detail": "Code MFA invalide", "code": "invalid_mfa_code"},
                )
            recovery.used_at = datetime.now(UTC)
        mfa.last_used_at = datetime.now(UTC)
        return await self._issue_tokens(user, user_agent=user_agent)
