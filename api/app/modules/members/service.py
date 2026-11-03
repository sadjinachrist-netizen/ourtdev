"""Logique métier — membres et annuaire."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import AuthContext
from app.modules.members.models import (
    Availability,
    Badge,
    MemberBadge,
    MemberMessage,
    MemberPii,
    MemberProfile,
    MemberStatus,
    MemberTechnology,
    ProfileVisibility,
    Technology,
)
from app.modules.members.schemas import (
    ApproveOut,
    BadgeAward,
    BadgeOut,
    DashboardItem,
    DashboardOut,
    DirectoryItem,
    MemberContactCreate,
    PiiOut,
    PiiUpsert,
    ProfileOut,
    ProfileUpsert,
    TechnologyCreate,
    TechnologyOut,
)
from app.modules.users.models import SiteSetting, User, UserStatus
from app.shared.activity import log_activity
from app.shared.i18n import pick_translation
from app.shared.pagination import Page, PageParams


class MembersService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _profile_query(self):
        return select(MemberProfile).options(
            selectinload(MemberProfile.technologies).selectinload(MemberTechnology.technology),
            selectinload(MemberProfile.badges).selectinload(MemberBadge.badge).selectinload(Badge.translations),
        )

    def _serialize(
        self,
        profile: MemberProfile,
        lang: str,
        *,
        owner: bool,
    ) -> ProfileOut:
        show_location = owner or profile.show_location
        show_links = owner or profile.show_links
        techs = [
            TechnologyOut(
                slug=link.technology.slug,
                name=link.technology.name,
                category=link.technology.category,
                level=link.level,
            )
            for link in profile.technologies
        ]
        badges: list[BadgeOut] = []
        for link in profile.badges:
            tr = pick_translation(link.badge.translations, lang)
            badges.append(
                BadgeOut(
                    code=link.badge.code,
                    name=tr.name if tr else link.badge.code,
                    edition_year=link.edition_year,
                )
            )
        return ProfileOut(
            user_id=profile.user_id,
            handle=profile.handle,
            display_name=profile.display_name,
            title=profile.title,
            bio=profile.bio,
            city=profile.city if show_location else None,
            country_code=profile.country_code if show_location else None,
            avatar_media_id=profile.avatar_media_id,
            member_status=profile.member_status.value if profile.member_status else None,
            availability=profile.availability.value,
            years_experience=profile.years_experience,
            github_url=profile.github_url if show_links else None,
            linkedin_url=profile.linkedin_url if show_links else None,
            portfolio_url=profile.portfolio_url if show_links else None,
            visibility=profile.visibility.value,
            listed_in_directory=profile.listed_in_directory,
            show_location=profile.show_location,
            show_links=profile.show_links,
            allow_contact=profile.allow_contact,
            technologies=techs,
            badges=badges,
        )

    def _visible_in_directory(self, profile: MemberProfile, viewer: AuthContext | None) -> bool:
        if not profile.listed_in_directory or profile.hidden_at is not None:
            return False
        if profile.visibility == ProfileVisibility.private:
            return False
        if profile.visibility == ProfileVisibility.members and viewer is None:
            return False
        return True

    async def _set_technologies(self, profile: MemberProfile, items: list) -> None:
        await self.db.execute(
            delete(MemberTechnology).where(MemberTechnology.user_id == profile.user_id)
        )
        for item in items:
            tech = (
                await self.db.execute(select(Technology).where(Technology.slug == item.slug))
            ).scalar_one_or_none()
            if tech is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"detail": f"Compétence inconnue: {item.slug}", "code": "unknown_technology"},
                )
            self.db.add(
                MemberTechnology(user_id=profile.user_id, technology_id=tech.id, level=item.level)
            )

    async def upsert_profile(self, auth: AuthContext, body: ProfileUpsert, lang: str) -> ProfileOut:
        profile = (
            await self.db.execute(self._profile_query().where(MemberProfile.user_id == auth.user.id))
        ).scalar_one_or_none()
        taken = (
            await self.db.execute(
                select(MemberProfile).where(
                    MemberProfile.handle == body.handle,
                    MemberProfile.user_id != auth.user.id,
                )
            )
        ).scalar_one_or_none()
        if taken is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"detail": "Handle déjà utilisé", "code": "handle_taken"},
            )

        consent_at = None
        if body.listed_in_directory:
            consent_at = (
                profile.directory_consent_at
                if profile and profile.directory_consent_at
                else datetime.now(UTC)
            )

        if profile is None:
            profile = MemberProfile(user_id=auth.user.id, handle=body.handle, display_name=body.display_name)
            self.db.add(profile)
        profile.handle = body.handle
        profile.display_name = body.display_name
        profile.title = body.title
        profile.bio = body.bio
        profile.city = body.city
        profile.country_code = body.country_code.upper() if body.country_code else None
        profile.avatar_media_id = body.avatar_media_id
        profile.member_status = MemberStatus(body.member_status) if body.member_status else None
        profile.availability = Availability(body.availability)
        profile.years_experience = body.years_experience
        profile.github_url = body.github_url
        profile.linkedin_url = body.linkedin_url
        profile.portfolio_url = body.portfolio_url
        profile.visibility = ProfileVisibility(body.visibility)
        profile.listed_in_directory = body.listed_in_directory
        profile.directory_consent_at = consent_at
        profile.show_location = body.show_location
        profile.show_links = body.show_links
        profile.allow_contact = body.allow_contact
        await self.db.flush()
        await self._set_technologies(profile, body.technologies)
        await log_activity(
            self.db,
            actor_id=auth.user.id,
            action="update",
            entity_type="member_profile",
            entity_id=str(auth.user.id),
        )
        await self.db.commit()
        profile = (
            await self.db.execute(self._profile_query().where(MemberProfile.user_id == auth.user.id))
        ).scalar_one()
        return self._serialize(profile, lang, owner=True)

    async def get_own_profile(self, auth: AuthContext, lang: str) -> ProfileOut:
        profile = (
            await self.db.execute(self._profile_query().where(MemberProfile.user_id == auth.user.id))
        ).scalar_one_or_none()
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Profil non créé", "code": "profile_missing"},
            )
        return self._serialize(profile, lang, owner=True)

    async def list_directory(
        self,
        *,
        lang: str,
        viewer: AuthContext | None,
        q: str | None,
        technology: str | None,
        city: str | None,
        country_code: str | None,
        member_status: str | None,
        params: PageParams,
    ) -> Page[DirectoryItem]:
        stmt = self._profile_query().where(
            MemberProfile.listed_in_directory.is_(True),
            MemberProfile.hidden_at.is_(None),
            MemberProfile.visibility != ProfileVisibility.private,
        )
        if viewer is None:
            stmt = stmt.where(MemberProfile.visibility == ProfileVisibility.public)
        if q:
            like = f"%{q.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(MemberProfile.handle).like(like),
                    func.lower(MemberProfile.display_name).like(like),
                )
            )
        if city:
            stmt = stmt.where(func.lower(MemberProfile.city) == city.lower())
        if country_code:
            stmt = stmt.where(MemberProfile.country_code == country_code.upper())
        if member_status:
            stmt = stmt.where(MemberProfile.member_status == MemberStatus(member_status))
        if technology:
            stmt = stmt.where(
                MemberProfile.technologies.any(
                    MemberTechnology.technology.has(Technology.slug == technology)
                )
            )

        total = (await self.db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        rows = (
            await self.db.execute(
                stmt.order_by(MemberProfile.display_name).offset(params.offset).limit(params.page_size)
            )
        ).scalars().unique().all()

        items: list[DirectoryItem] = []
        for profile in rows:
            public = self._serialize(profile, lang, owner=False)
            items.append(
                DirectoryItem(
                    handle=public.handle,
                    display_name=public.display_name,
                    title=public.title,
                    city=public.city,
                    country_code=public.country_code,
                    member_status=public.member_status,
                    avatar_media_id=public.avatar_media_id,
                    technologies=[t.slug for t in public.technologies],
                    badges=[b.code for b in public.badges],
                )
            )
        return Page.of(items, total, params)

    async def get_public_profile(
        self, handle: str, lang: str, viewer: AuthContext | None
    ) -> ProfileOut:
        profile = (
            await self.db.execute(self._profile_query().where(MemberProfile.handle == handle))
        ).scalar_one_or_none()
        if profile is None or not self._visible_in_directory(profile, viewer):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Profil introuvable", "code": "profile_not_found"},
            )
        owner = viewer is not None and viewer.user.id == profile.user_id
        return self._serialize(profile, lang, owner=owner)

    async def upsert_pii(self, auth: AuthContext, body: PiiUpsert) -> PiiOut:
        row = (
            await self.db.execute(select(MemberPii).where(MemberPii.user_id == auth.user.id))
        ).scalar_one_or_none()
        if row is None:
            row = MemberPii(user_id=auth.user.id)
            self.db.add(row)
        row.first_name = body.first_name
        row.last_name = body.last_name
        row.phone = body.phone
        await self.db.commit()
        await self.db.refresh(row)
        return PiiOut(
            user_id=row.user_id,
            first_name=row.first_name,
            last_name=row.last_name,
            phone=row.phone,
        )

    async def get_own_pii(self, auth: AuthContext) -> PiiOut:
        row = (
            await self.db.execute(select(MemberPii).where(MemberPii.user_id == auth.user.id))
        ).scalar_one_or_none()
        if row is None:
            return PiiOut(user_id=auth.user.id)
        return PiiOut(
            user_id=row.user_id,
            first_name=row.first_name,
            last_name=row.last_name,
            phone=row.phone,
        )

    async def get_pii_admin(self, user_id: uuid.UUID) -> PiiOut:
        row = (
            await self.db.execute(select(MemberPii).where(MemberPii.user_id == user_id))
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Données personnelles absentes", "code": "pii_not_found"},
            )
        return PiiOut(
            user_id=row.user_id,
            first_name=row.first_name,
            last_name=row.last_name,
            phone=row.phone,
        )

    async def contact_member(
        self,
        handle: str,
        body: MemberContactCreate,
        viewer: AuthContext | None,
    ) -> None:
        if body.website:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "Requête rejetée", "code": "spam_detected"},
            )
        profile = (
            await self.db.execute(select(MemberProfile).where(MemberProfile.handle == handle))
        ).scalar_one_or_none()
        if profile is None or not self._visible_in_directory(profile, viewer) or not profile.allow_contact:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Contact indisponible", "code": "contact_unavailable"},
            )
        self.db.add(
            MemberMessage(
                recipient_id=profile.user_id,
                sender_user_id=viewer.user.id if viewer else None,
                sender_name=body.name,
                sender_email=str(body.email).lower(),
                subject=body.subject,
                message=body.message,
            )
        )
        await self.db.commit()

    async def dashboard(self, auth: AuthContext) -> DashboardOut:
        uid = auth.user.id
        events = (
            await self.db.execute(
                text(
                    """
                    SELECT e.id::text, COALESCE(et.title, e.slug), e.slug
                    FROM event_participants ep
                    JOIN events e ON e.id = ep.event_id
                    LEFT JOIN event_translations et
                      ON et.event_id = e.id AND et.language_code = 'fr'
                    WHERE ep.user_id = :uid
                    ORDER BY e.starts_at DESC
                    """
                ),
                {"uid": uid},
            )
        ).all()
        projects = (
            await self.db.execute(
                text(
                    """
                    SELECT p.id::text, p.name, p.slug
                    FROM project_contributors pc
                    JOIN projects p ON p.id = pc.project_id
                    WHERE pc.user_id = :uid
                    ORDER BY pc.joined_at DESC
                    """
                ),
                {"uid": uid},
            )
        ).all()
        resources = (
            await self.db.execute(
                text(
                    """
                    SELECT r.id::text, COALESCE(rt.title, r.type::text), NULL
                    FROM resources r
                    LEFT JOIN resource_translations rt
                      ON rt.resource_id = r.id AND rt.language_code = 'fr'
                    WHERE r.created_by = :uid
                    ORDER BY r.created_at DESC
                    """
                ),
                {"uid": uid},
            )
        ).all()
        return DashboardOut(
            events=[DashboardItem(id=r[0], kind="event", title=r[1], slug=r[2]) for r in events],
            projects=[DashboardItem(id=r[0], kind="project", title=r[1], slug=r[2]) for r in projects],
            resources=[DashboardItem(id=r[0], kind="resource", title=r[1], slug=r[2]) for r in resources],
        )

    async def list_technologies(self) -> list[TechnologyOut]:
        rows = (await self.db.execute(select(Technology).order_by(Technology.name))).scalars().all()
        return [TechnologyOut(slug=t.slug, name=t.name, category=t.category) for t in rows]

    async def create_technology(self, body: TechnologyCreate, auth: AuthContext) -> TechnologyOut:
        exists = (
            await self.db.execute(select(Technology).where(Technology.slug == body.slug))
        ).scalar_one_or_none()
        if exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"detail": "Compétence déjà existante", "code": "technology_exists"},
            )
        tech = Technology(slug=body.slug, name=body.name, category=body.category)
        self.db.add(tech)
        await log_activity(
            self.db,
            actor_id=auth.user.id,
            action="create",
            entity_type="technology",
            entity_id=body.slug,
        )
        await self.db.commit()
        await self.db.refresh(tech)
        return TechnologyOut(slug=tech.slug, name=tech.name, category=tech.category)

    async def _validation_mode(self) -> str:
        row = (
            await self.db.execute(select(SiteSetting).where(SiteSetting.key == "member_validation"))
        ).scalar_one_or_none()
        if row is None:
            return "email"
        value = row.value
        return value.strip('"') if isinstance(value, str) else str(value)

    async def approve(self, user_id: uuid.UUID, auth: AuthContext) -> ApproveOut:
        user = (await self.db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Utilisateur introuvable", "code": "user_not_found"},
            )
        mode = await self._validation_mode()
        user.approved_at = datetime.now(UTC)
        user.approved_by = auth.user.id
        if mode == "admin" or (mode == "both" and user.email_verified_at) or (
            mode == "email" and user.email_verified_at
        ):
            user.status = UserStatus.active
        await log_activity(
            self.db,
            actor_id=auth.user.id,
            action="approve",
            entity_type="user",
            entity_id=str(user.id),
        )
        await self.db.commit()
        await self.db.refresh(user)
        return ApproveOut(user_id=user.id, status=user.status.value, approved_at=user.approved_at)

    async def set_hidden(self, user_id: uuid.UUID, hidden: bool, auth: AuthContext) -> ProfileOut:
        profile = (
            await self.db.execute(self._profile_query().where(MemberProfile.user_id == user_id))
        ).scalar_one_or_none()
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Profil introuvable", "code": "profile_not_found"},
            )
        profile.hidden_at = datetime.now(UTC) if hidden else None
        profile.hidden_by = auth.user.id if hidden else None
        await log_activity(
            self.db,
            actor_id=auth.user.id,
            action="hide" if hidden else "unhide",
            entity_type="member_profile",
            entity_id=str(user_id),
        )
        await self.db.commit()
        profile = (
            await self.db.execute(self._profile_query().where(MemberProfile.user_id == user_id))
        ).scalar_one()
        return self._serialize(profile, "fr", owner=True)

    async def award_badge(self, user_id: uuid.UUID, body: BadgeAward, auth: AuthContext) -> ProfileOut:
        profile = (
            await self.db.execute(self._profile_query().where(MemberProfile.user_id == user_id))
        ).scalar_one_or_none()
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Profil introuvable", "code": "profile_not_found"},
            )
        badge = (await self.db.execute(select(Badge).where(Badge.code == body.code))).scalar_one_or_none()
        if badge is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Badge inconnu", "code": "badge_not_found"},
            )
        existing = (
            await self.db.execute(
                select(MemberBadge).where(
                    MemberBadge.user_id == user_id, MemberBadge.badge_id == badge.id
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            self.db.add(
                MemberBadge(
                    user_id=user_id,
                    badge_id=badge.id,
                    edition_year=body.edition_year,
                    awarded_by=auth.user.id,
                )
            )
        await log_activity(
            self.db,
            actor_id=auth.user.id,
            action="award_badge",
            entity_type="member_profile",
            entity_id=str(user_id),
            changes={"badge": body.code},
        )
        await self.db.commit()
        self.db.expire_all()
        profile = (
            await self.db.execute(self._profile_query().where(MemberProfile.user_id == user_id))
        ).scalar_one()
        return self._serialize(profile, "fr", owner=True)

    async def export_csv(self, *, include_pii: bool) -> str:
        rows = (
            await self.db.execute(
                select(MemberProfile, User.email)
                .join(User, User.id == MemberProfile.user_id)
                .order_by(MemberProfile.display_name)
            )
        ).all()
        buf = io.StringIO()
        writer = csv.writer(buf)
        header = [
            "handle",
            "display_name",
            "title",
            "city",
            "country_code",
            "member_status",
            "email",
            "listed_in_directory",
        ]
        if include_pii:
            header.extend(["first_name", "last_name", "phone"])
        writer.writerow(header)
        for profile, email in rows:
            line = [
                profile.handle,
                profile.display_name,
                profile.title or "",
                profile.city or "",
                profile.country_code or "",
                profile.member_status.value if profile.member_status else "",
                email,
                "true" if profile.listed_in_directory else "false",
            ]
            if include_pii:
                pii = (
                    await self.db.execute(select(MemberPii).where(MemberPii.user_id == profile.user_id))
                ).scalar_one_or_none()
                line.extend(
                    [
                        pii.first_name if pii else "",
                        pii.last_name if pii else "",
                        pii.phone if pii else "",
                    ]
                )
            writer.writerow(line)
        return buf.getvalue()
