"""Logique métier — module 6 (ressources).
By admin + lecteurs, avec filtrage, arborescence, traductions.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.resources.models import (
    AccessLevel,
    ContentStatus,
    Resource,
    ResourceFolder,
    ResourceFolderTranslation,
    ResourceType,
)
from app.modules.resources.schemas import ResourceOut
from app.modules.users.models import User


class FolderTree:
    """Nœud de l'arborescence retourné."""

    def __init__(self, folder: ResourceFolder):
        self.id: str = str(folder.id)
        self.slug: str = folder.slug
        self.parent_id: str | None = str(folder.parent_id) if folder.parent_id else None
        self.event_id: str | None = str(folder.event_id) if folder.event_id else None
        self.program_id: str | None = str(folder.program_id) if folder.program_id else None
        self.edition_year: int | None = folder.edition_year
        self.access_level: AccessLevel = folder.access_level
        self.status: ContentStatus = folder.status
        self.published_at: str | None = (
            folder.published_at.isoformat() if folder.published_at else None
        )
        self.path: list[str] = []
        self.children: list[FolderTree] = []
        self.resource_count: int = 0
        self.child_count: int = 0
        self.translated_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "slug": self.slug,
            "parent_id": self.parent_id,
            "event_id": self.event_id,
            "program_id": self.program_id,
            "edition_year": self.edition_year,
            "access_level": self.access_level.value,
            "status": self.status.value,
            "published_at": self.published_at,
            "path": self.path,
            "child_count": self.child_count,
            "resource_count": self.resource_count,
            "translated_name": self.translated_name,
        }


class ResourcesService:
    """Service du module resources (par admin et par lecteurs authentifiés)."""

    # --- Dossiers -------------------------------------------------------

    async def list_folders(
        self,
        db: AsyncSession,
        *,
        event_id: str | None = None,
        program_id: str | None = None,
        edition_year: int | None = None,
        access_level: AccessLevel | None = None,
        status: ContentStatus | None = None,
        user: User | None = None,
        lang: str,
    ) -> list[FolderTree]:
        stmt = select(ResourceFolder).order_by(ResourceFolder.position, ResourceFolder.slug)
        if event_id:
            stmt = stmt.where(ResourceFolder.event_id == event_id)
        if program_id:
            stmt = stmt.where(ResourceFolder.program_id == program_id)
        if edition_year is not None:
            stmt = stmt.where(ResourceFolder.edition_year == edition_year)
        if access_level is not None:
            stmt = stmt.where(ResourceFolder.access_level == access_level)
        if status is not None:
            stmt = stmt.where(ResourceFolder.status == status)

        rows = (await db.execute(stmt)).scalars().all()
        return self._build_folder_trees(rows, db, lang, user)

    async def get_folder(
        self, db: AsyncSession, folder_id: str, lang: str
    ) -> FolderTree | None:
        stmt = (
            select(ResourceFolder)
            .options(selectinload(ResourceFolder.translations))
            .where(ResourceFolder.id == folder_id)
        )
        row = (await db.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return self._build_folder_tree(row, db, lang)

    def _build_folder_tree(
        self, folder: ResourceFolder, db: AsyncSession, lang: str, user: User | None = None
    ) -> FolderTree:
        tree = FolderTree(folder)
        tree.path = self._build_path(folder)
        tree.child_count = self._count_children(folder, db)
        tree.resource_count = self._count_resources(folder, db)

        trans = self._get_translation(folder.translations, lang)
        if trans:
            tree.translated_name = trans.name

        return tree

    def _build_folder_trees(
        self, folders: list[ResourceFolder], db: AsyncSession, lang: str, user: User | None = None
    ) -> list[FolderTree]:
        roots: dict[str, FolderTree] = {}
        all_trees: dict[str, FolderTree] = {}

        for folder in folders:
            tree = self._build_folder_tree(folder, db, lang, user)
            all_trees[str(tree.id)] = tree
            if folder.parent_id is None:
                roots[str(tree.id)] = tree
            else:
                parent = all_trees.get(str(folder.parent_id))
                if parent:
                    parent.children.append(tree)

        return list(roots.values())

    def _build_path(self, folder: ResourceFolder) -> list[str]:
        path: list[str] = []
        current: ResourceFolder | None = folder
        while current is not None:
            path.insert(0, current.slug)
            current = current.parent
        return path

    @staticmethod
    def _count_children(folder: ResourceFolder, db: AsyncSession) -> int:
        stmt = select(func.count(ResourceFolder.id)).where(
            ResourceFolder.parent_id == folder.id
        )
        result = db.execute(stmt).scalar_one()
        return int(result or 0)

    @staticmethod
    def _count_resources(folder: ResourceFolder, db: AsyncSession) -> int:
        stmt = select(func.count(Resource.id)).where(Resource.folder_id == folder.id)
        result = db.execute(stmt).scalar_one()
        return int(result or 0)

    @staticmethod
    def _get_translation(translations: list[ResourceFolderTranslation], lang: str) -> Any | None:
        for t in translations:
            if t.language_code == lang:
                return t
        return None

    # --- Ressources -----------------------------------------------------

    async def list_resources(
        self,
        db: AsyncSession,
        *,
        folder_id: str | None = None,
        type: ResourceType | None = None,
        access_level: AccessLevel | None = None,
        status: ContentStatus | None = None,
        year: int | None = None,
        event_id: str | None = None,
        user: User | None = None,
        lang: str,
    ) -> list[ResourceOut]:
        stmt = (
            select(Resource)
            .options(selectinload(Resource.translations))
            .options(selectinload(Resource.tags))
            .order_by(Resource.position, Resource.type)
        )
        if folder_id:
            stmt = stmt.where(Resource.folder_id == folder_id)
        if type is not None:
            stmt = stmt.where(Resource.type == type)
        if access_level is not None:
            stmt = stmt.where(Resource.access_level == access_level)
        if status is not None:
            stmt = stmt.where(Resource.status == status)
        if year is not None:
            stmt = stmt.where(
                or_(
                    Resource.folder.has(ResourceFolder.edition_year == year),
                    Resource.folder.has(ResourceFolder.event_id.isnot(None)),
                )
            )
        if event_id:
            stmt = stmt.where(Resource.folder.has(ResourceFolder.event_id == event_id))

        rows = (await db.execute(stmt)).scalars().all()
        return [self._to_resource_out(r, lang) for r in rows]

    async def get_resource(self, db: AsyncSession, resource_id: str, lang: str) -> ResourceOut | None:
        stmt = (
            select(Resource)
            .options(selectinload(Resource.translations))
            .options(selectinload(Resource.tags))
            .where(Resource.id == resource_id)
        )
        row = (await db.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return self._to_resource_out(row, lang)

    async def create_folder(
        self, db: AsyncSession, *, data: dict[str, Any], user: User
    ) -> ResourceFolder:
        folder = ResourceFolder(**data)
        db.add(folder)
        await db.flush()
        await self._create_translations(folder, data.get("translations", []), db, user, lang="fr")
        return folder

    async def update_folder(
        self, db: AsyncSession, folder_id: str, data: dict[str, Any], user: User
    ) -> ResourceFolder | None:
        stmt = select(ResourceFolder).where(ResourceFolder.id == folder_id)
        folder = (await db.execute(stmt)).scalar_one_or_none()
        if folder is None:
            return None
        for key, value in data.items():
            if hasattr(folder, key) and key not in ("id", "translations"):
                setattr(folder, key, value)
        await db.flush()
        return folder

    async def delete_folder(self, db: AsyncSession, folder_id: str) -> bool:
        stmt = select(ResourceFolder).where(ResourceFolder.id == folder_id)
        folder = (await db.execute(stmt)).scalar_one_or_none()
        if folder is None:
            return False
        await db.delete(folder)
        return True

    # --- Helpers généraux ----------------------------------------------

    @staticmethod
    def _to_resource_out(resource: Resource, lang: str) -> ResourceOut:
        title = None
        for t in resource.translations:
            if t.language_code == lang:
                title = t.title
                break
        return ResourceOut(
            id=str(resource.id),
            folder_id=str(resource.folder_id),
            type=resource.type,
            title=title,
            description=resource.translations[0].description if resource.translations else None,
            access_level=resource.access_level,
            view_count=resource.view_count,
            download_count=resource.download_count,
            status=resource.status,
            published_at=resource.published_at.isoformat() if resource.published_at else None,
            media_id=str(resource.media_id) if resource.media_id else None,
            url=resource.url,
            speaker_id=str(resource.speaker_id) if resource.speaker_id else None,
        )
