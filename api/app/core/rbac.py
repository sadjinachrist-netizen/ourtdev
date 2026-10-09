from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.users.models import Permission, Role, RolePermission, User, UserRole


async def get_user_permission_codes(db: AsyncSession, user_id: uuid.UUID) -> set[str]:
    stmt = (
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user_id)
    )
    result = await db.execute(stmt)
    return set(result.scalars().all())


async def get_user_roles(db: AsyncSession, user_id: uuid.UUID) -> list[UserRole]:
    stmt = (
        select(UserRole)
        .where(UserRole.user_id == user_id)
        .options(selectinload(UserRole.role), selectinload(UserRole.community))
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def user_has_role(db: AsyncSession, user_id: uuid.UUID, role_code: str) -> bool:
    stmt = (
        select(UserRole.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(UserRole.user_id == user_id, Role.code == role_code)
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


async def load_user(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
