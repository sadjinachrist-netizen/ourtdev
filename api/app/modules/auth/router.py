"""Routes FastAPI — auth."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, status

from app.core.dependencies import CurrentAuth, DbSession, AppSettings
from app.modules.auth.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    MfaEnableRequest,
    MfaEnableResponse,
    MfaRequiredResponse,
    MfaSetupResponse,
    MfaVerifyRequest,
    OAuthAuthorizeResponse,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserPublic,
    VerifyEmailRequest,
)
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _service(db: DbSession, settings: AppSettings) -> AuthService:
    return AuthService(db, settings)


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Inscription email + mot de passe",
)
async def register(
    body: RegisterRequest,
    db: DbSession,
    settings: AppSettings,
) -> UserPublic:
    user = await _service(db, settings).register(
        email=str(body.email),
        password=body.password,
        preferred_language=body.preferred_language,
    )
    return UserPublic.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse | MfaRequiredResponse,
    summary="Connexion email + mot de passe",
)
async def login(
    body: LoginRequest,
    request: Request,
    db: DbSession,
    settings: AppSettings,
) -> dict[str, Any]:
    return await _service(db, settings).login(
        email=str(body.email),
        password=body.password,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/refresh", response_model=TokenResponse, summary="Renouveler les jetons")
async def refresh(
    body: RefreshRequest,
    request: Request,
    db: DbSession,
    settings: AppSettings,
) -> dict[str, str]:
    return await _service(db, settings).refresh(
        refresh_token=body.refresh_token,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/logout", response_model=MessageResponse, summary="Révoquer le refresh token")
async def logout(
    body: RefreshRequest,
    db: DbSession,
    settings: AppSettings,
) -> MessageResponse:
    await _service(db, settings).logout(refresh_token=body.refresh_token)
    return MessageResponse(detail="Déconnecté", code="logged_out")


@router.post("/verify-email", response_model=UserPublic, summary="Vérifier l'email")
async def verify_email(
    body: VerifyEmailRequest,
    db: DbSession,
    settings: AppSettings,
) -> UserPublic:
    user = await _service(db, settings).verify_email(token=body.token)
    return UserPublic.model_validate(user)


@router.post("/forgot-password", response_model=MessageResponse, summary="Demander un reset")
async def forgot_password(
    body: ForgotPasswordRequest,
    db: DbSession,
    settings: AppSettings,
) -> MessageResponse:
    await _service(db, settings).forgot_password(email=str(body.email))
    return MessageResponse(detail="Si le compte existe, un email a été envoyé", code="ok")


@router.post("/reset-password", response_model=MessageResponse, summary="Réinitialiser le mot de passe")
async def reset_password(
    body: ResetPasswordRequest,
    db: DbSession,
    settings: AppSettings,
) -> MessageResponse:
    await _service(db, settings).reset_password(token=body.token, new_password=body.new_password)
    return MessageResponse(detail="Mot de passe mis à jour", code="password_reset")


@router.get(
    "/oauth/{provider}/authorize",
    response_model=OAuthAuthorizeResponse,
    summary="URL d'autorisation OAuth",
)
async def oauth_authorize(
    provider: str,
    db: DbSession,
    settings: AppSettings,
) -> OAuthAuthorizeResponse:
    url = _service(db, settings).oauth_authorize_url(provider)
    return OAuthAuthorizeResponse(authorize_url=url, provider=provider)


@router.get(
    "/oauth/{provider}/callback",
    response_model=TokenResponse,
    summary="Callback OAuth",
)
async def oauth_callback(
    provider: str,
    request: Request,
    db: DbSession,
    settings: AppSettings,
    code: Annotated[str, Query()],
) -> dict[str, str]:
    return await _service(db, settings).oauth_callback(
        provider=provider,
        code=code,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/mfa/setup", response_model=MfaSetupResponse, summary="Initialiser MFA TOTP")
async def mfa_setup(
    auth: CurrentAuth,
    db: DbSession,
    settings: AppSettings,
) -> MfaSetupResponse:
    data = await _service(db, settings).mfa_setup(auth.user)
    return MfaSetupResponse(**data)


@router.post("/mfa/enable", response_model=MfaEnableResponse, summary="Activer MFA")
async def mfa_enable(
    body: MfaEnableRequest,
    auth: CurrentAuth,
    db: DbSession,
    settings: AppSettings,
) -> MfaEnableResponse:
    codes = await _service(db, settings).mfa_enable(auth.user, body.code)
    return MfaEnableResponse(recovery_codes=codes)


@router.post("/mfa/verify", response_model=TokenResponse, summary="Valider MFA au login")
async def mfa_verify(
    body: MfaVerifyRequest,
    request: Request,
    db: DbSession,
    settings: AppSettings,
) -> dict[str, str]:
    return await _service(db, settings).mfa_verify(
        mfa_ticket=body.mfa_ticket,
        code=body.code,
        user_agent=request.headers.get("user-agent"),
    )


@router.get("/status", summary="Stub statut module auth")
async def auth_status() -> dict[str, str]:
    return {"module": "auth", "status": "ready"}
