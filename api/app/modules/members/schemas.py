"""Schémas Pydantic — members."""

from pydantic import BaseModel


class MembersStatus(BaseModel):
    module: str = "members"
    status: str = "not_implemented"
