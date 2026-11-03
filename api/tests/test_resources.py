"""Tests module 6 — resources (unit + integration).
Prérequis : PostgreSQL démarré (docker compose up -d).
"""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import (AsyncSession, create_async_engine, async_sessionmaker)

from app.core.database import Base, AsyncSessionLocal
from app.modules.resources.models import (
    AccessLevel,
    ContentStatus,
    Resource,
    ResourceFolder,
    ResourceFolderTranslation,
    ResourceType,
)
from app.modules.resources.service import ResourcesService

pytestmark = pytest.mark.asyncio

TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/ourtdev_test"

service = ResourcesService()

@pytest.fixture(autouse=True)
async def test_db():
    """Fixture : base de données de test distante (test_resources)."""
    from app.core.config import get_settings
    get_settings().database_url = TEST_DATABASE_URL
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(bind=engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()


# === Fixtures de données de test
@pytest.fixture
async def sample_folder(db):
    """Dossier racine de test."""
    folder = ResourceFolder(slug="ressources", access_level=AccessLevel.public, status=ContentStatus.published)
    db.add(folder)
    await db.flush()
    tr = ResourceFolderTranslation(folder_id=folder.id, language_code="fr", name="Ressources")
    db.add(tr)
    await db.flush()
    return folder


# === Tests unitaires — service

class TestFolderService:
    """Tests unitaires de la logique des dossiers (service)."""

    async def test_list_folders_returns_trees(self, db, sample_folder):
        child = ResourceFolder(slug="fils", parent_id=sample_folder.id)
        db.add(child)
        await db.flush()

        trees = await service.list_folders(db, lang="fr", user=None)
        assert len(trees) >= 1
        assert any(t.slug == "fils" for t in trees)

    async def test_get_folder_returns_tree(self, db, sample_folder):
        tree = await service.get_folder(db, sample_folder.id, lang="fr")
        assert tree is not None
        assert tree.slug == "ressources"
        assert tree.resource_count == 0

    async def test_get_folder_not_found(self, db):
        tree = await service.get_folder(db, str(uuid.uuid4()), lang="fr")
        assert tree is None


class TestResourceService:
    """Tests unitaires de la logique des ressources (service)."""

    async def test_create_and_get_resource(self, db, sample_folder):
        res = Resource(folder_id=sample_folder.id, type=ResourceType.slides, access_level=AccessLevel.public, status=ContentStatus.published, title="Amphi A", description="Présentation", url="https://example.com/seminar")
        db.add(res)
        await db.flush()

        out = await service.get_resource(db, str(res.id), lang="fr")
        assert out is not None
        assert out.type == ResourceType.slides
        assert out.title == "Amphi A"
        assert out.access_level == AccessLevel.public
        assert out.status == ContentStatus.published
        assert out.media_id is None
        assert out.url == "https://example.com/seminar"

    async def test_list_resources_filter_by_type(self, db, sample_folder):
        res1 = Resource(folder_id=sample_folder.id, type=ResourceType.slides, url="https://slides.example.com")
        res2 = Resource(folder_id=sample_folder.id, type=ResourceType.video, url="https://video.example.com")
        db.add_all([res1, res2])
        await db.flush()

        results = await service.list_resources(db, folder_id=str(sample_folder.id), type=ResourceType.slides, lang="fr")
        assert len(results) == 1
        assert results[0].type == ResourceType.slides
        assert results[0].url == "https://slides.example.com"

    async def test_delete_folder_cascade(self, db, sample_folder):
        child = ResourceFolder(slug="enfant", parent_id=sample_folder.id)
        db.add(child)
        await db.flush()
        assert child.id is not None

        ok = await service.delete_folder(db, sample_folder.id)
        assert ok is True


# === Tests d'intégration — routes API

@pytest.mark.asyncio
async def test_resources_status(client):
    """Statut public du module resources."""
    resp = await client.get("/resources/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["module"] == "resources"
    assert data["status"] == "ready"

@pytest.mark.asyncio
async def test_list_folders_empty(client, db):
    """Lorsqu'aucun dossier n'existe, la liste est vide."""
    resp = await client.get("/resources/folders")
    assert resp.status_code == 200
    assert resp.json() == []

@pytest.mark.asyncio
async def test_list_resources_empty(client, db):
    """Lorsqu'aucune ressource n'existe, la liste est vide."""
    resp = await client.get("/resources/resources")
    assert resp.status_code == 200
    assert resp.json() == []