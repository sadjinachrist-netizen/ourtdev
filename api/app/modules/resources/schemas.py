"""Schémas Pydantic — resources."""

from pydantic import BaseModel


class ResourcesStatus(BaseModel):
    module: str = "resources"
    status: str = "not_implemented"
