"""Schémas Pydantic — auth."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    preferred_language: str | None = Field(default="fr", max_length=5)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MfaRequiredResponse(BaseModel):
    mfa_required: bool = True
    mfa_ticket: str
    detail: str = "Double authentification requise"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class VerifyEmailRequest(BaseModel):
    token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class OAuthAuthorizeResponse(BaseModel):
    authorize_url: str
    provider: str


class MfaSetupResponse(BaseModel):
    secret: str
    otpauth_url: str


class MfaEnableRequest(BaseModel):
    code: str = Field(min_length=6, max_length=8)


class MfaEnableResponse(BaseModel):
    enabled: bool = True
    recovery_codes: list[str]


class MfaVerifyRequest(BaseModel):
    mfa_ticket: str
    code: str = Field(min_length=6, max_length=64)


class MessageResponse(BaseModel):
    detail: str
    code: str = "ok"


class UserPublic(BaseModel):
    id: uuid.UUID
    email: EmailStr
    status: str
    email_verified_at: datetime | None
    preferred_language: str | None

    model_config = {"from_attributes": True}
