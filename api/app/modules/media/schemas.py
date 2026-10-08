"""Schémas Pydantic — media."""

from pydantic import BaseModel


class MediaStatus(BaseModel):
    module: str = "media"
    status: str = "not_implemented"
