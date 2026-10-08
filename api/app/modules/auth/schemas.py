"""Schémas Pydantic — auth."""

from pydantic import BaseModel


class AuthStatus(BaseModel):
    module: str = "auth"
    status: str = "not_implemented"
