"""Schémas Pydantic — contents."""

from pydantic import BaseModel


class ContentsStatus(BaseModel):
    module: str = "contents"
    status: str = "not_implemented"
