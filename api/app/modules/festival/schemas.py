"""Schémas Pydantic — festival."""

from pydantic import BaseModel


class FestivalStatus(BaseModel):
    module: str = "festival"
    status: str = "not_implemented"
