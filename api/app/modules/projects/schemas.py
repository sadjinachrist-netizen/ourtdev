"""Schémas Pydantic — projects."""

from pydantic import BaseModel


class ProjectsStatus(BaseModel):
    module: str = "projects"
    status: str = "not_implemented"
