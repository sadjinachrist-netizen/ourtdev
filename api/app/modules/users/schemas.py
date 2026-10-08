"""Schémas Pydantic — users."""

from pydantic import BaseModel


class UsersStatus(BaseModel):
    module: str = "users"
    status: str = "not_implemented"
