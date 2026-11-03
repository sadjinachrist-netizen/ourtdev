"""Logique métier — module 1 contenus."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import AuthContext
from app.modules.contents.models import (
    Article,
    ArticleTag,
    ArticleTranslation,
    ContactMessage,
    ContentStatus,
    KeyFigure,
    KeyFigureTranslation,
    Page,
    PageTranslation,
    Partner,
    PartnerLevel,
    PartnerTranslation,
    TeamMember,
    TeamMemberTranslation,
)
from app.modules.contents.schemas import (
    ArticleCreate,
    ArticleOut,
    ArticleUpdate,
    ContactCreate,
    ContactOut,
    EventTeaserOut,
    HomeOut,
    KeyFigureOut,
    KeyFigureUpdate,
    PageAdminOut,
    PageCreate,
    PageOut,
    PageUpdate,
    PartnerCreate,
    PartnerOut,
    PartnerUpdate,
    TeamMemberCreate,
    TeamMemberOut,
    TeamMemberUpdate,
    TranslationIn,
)
from app.modules.events.models import Event
from app.shared.activity import log_activity
from app.shared.i18n import pick_translation
from app.shared.publishing import now_utc, published_filter


class ContentsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ----- serializers -----

    def _page_out(self, page: Page, lang: str) -> PageOut | None:
        tr = pick_translation(page.translations, lang)
        if tr is None:
            return None
        return PageOut(
            id=page.id,
            slug=page.slug,
            status=page.status.value,
            published_at=page.published_at,
            language=tr.language_code,
            title=tr.title,
            summary=tr.summary,
            body=tr.body,
            meta_title=tr.meta_title,
            meta_description=tr.meta_description,
        )

    def _partner_out(self, partner: Partner, lang: str) -> PartnerOut:
        tr = pick_translation(partner.translations, lang)
        level_name = None
        level_code = None
        if partner.level:
            level_code = partner.level.code
            ltr = pick_translation(partner.level.translations, lang)
            level_name = ltr.name if ltr else None
        return PartnerOut(
            id=partner.id,
            slug=partner.slug,
            name=partner.name,
            website_url=partner.website_url,
            logo_media_id=partner.logo_media_id,
            show_on_home=partner.show_on_home,
            position=partner.position,
            level_code=level_code,
            level_name=level_name,
            language=tr.language_code if tr else lang,
            description=tr.description if tr else None,
        )

    def _article_out(self, article: Article, lang: str) -> ArticleOut | None:
        tr = pick_translation(article.translations, lang)
        if tr is None:
            return None
        return ArticleOut(
            id=article.id,
            slug=article.slug,
            status=article.status.value,
            published_at=article.published_at,
            category_id=article.category_id,
            cover_media_id=article.cover_media_id,
            language=tr.language_code,
            title=tr.title,
            excerpt=tr.excerpt,
            body=tr.body,
            tags=[t.name for t in article.tags],
        )

    def _team_out(self, member: TeamMember, lang: str) -> TeamMemberOut | None:
        tr = pick_translation(member.translations, lang)
        if tr is None:
            return None
        return TeamMemberOut(
            id=member.id,
            full_name=member.full_name,
            team_group=member.team_group,
            linkedin_url=member.linkedin_url,
            position=member.position,
            photo_media_id=member.photo_media_id,
            language=tr.language_code,
            role_title=tr.role_title,
            bio=tr.bio,
        )

    def _figure_out(self, fig: KeyFigure, lang: str) -> KeyFigureOut | None:
        tr = pick_translation(fig.translations, lang)
        if tr is None:
            return None
        return KeyFigureOut(
            id=fig.id,
            code=fig.code,
            value=fig.value,
            suffix=fig.suffix,
            language=tr.language_code,
            label=tr.label,
            position=fig.position,
        )

    def _event_out(self, event: Event, lang: str) -> EventTeaserOut | None:
        tr = pick_translation(event.translations, lang)
        if tr is None:
            return None
        return EventTeaserOut(
            id=event.id,
            slug=event.slug,
            starts_at=event.starts_at,
            city=event.city,
            language=tr.language_code,
            title=tr.title,
            summary=tr.summary,
        )

    # ----- public -----

    async def get_home(self, lang: str) -> HomeOut:
        page = (
            await self.db.execute(
                select(Page)
                .where(Page.slug == "accueil", published_filter(Page.status, Page.published_at))
                .options(selectinload(Page.translations))
            )
        ).scalar_one_or_none()

        figures = (
            await self.db.execute(
                select(KeyFigure)
                .where(
                    KeyFigure.show_on_home.is_(True),
                    KeyFigure.is_active.is_(True),
                    KeyFigure.edition_year.is_(None),
                    KeyFigure.program_id.is_(None),
                )
                .options(selectinload(KeyFigure.translations))
                .order_by(KeyFigure.position)
            )
        ).scalars().all()

        partners = (
            await self.db.execute(
                select(Partner)
                .where(Partner.show_on_home.is_(True), Partner.is_active.is_(True))
                .options(
                    selectinload(Partner.translations),
                    selectinload(Partner.level).selectinload(PartnerLevel.translations),
                )
                .order_by(Partner.position)
            )
        ).scalars().all()

        events = (
            await self.db.execute(
                select(Event)
                .where(
                    published_filter(Event.status, Event.published_at),
                    Event.starts_at >= now_utc(),
                )
                .options(selectinload(Event.translations))
                .order_by(Event.starts_at.asc())
                .limit(3)
            )
        ).scalars().all()

        articles = (
            await self.db.execute(
                select(Article)
                .where(published_filter(Article.status, Article.published_at))
                .options(selectinload(Article.translations), selectinload(Article.tags))
                .order_by(Article.published_at.desc())
                .limit(3)
            )
        ).scalars().all()

        return HomeOut(
            page=self._page_out(page, lang) if page else None,
            key_figures=[f for fig in figures if (f := self._figure_out(fig, lang))],
            partners=[self._partner_out(p, lang) for p in partners],
            upcoming_events=[e for ev in events if (e := self._event_out(ev, lang))],
            latest_articles=[a for art in articles if (a := self._article_out(art, lang))],
        )

    async def get_page(self, slug: str, lang: str, *, public: bool = True) -> PageOut:
        stmt = select(Page).where(Page.slug == slug).options(selectinload(Page.translations))
        if public:
            stmt = stmt.where(published_filter(Page.status, Page.published_at))
        page = (await self.db.execute(stmt)).scalar_one_or_none()
        if page is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Page introuvable", "code": "page_not_found"},
            )
        out = self._page_out(page, lang)
        if out is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Traduction indisponible", "code": "translation_missing"},
            )
        return out

    async def list_team(self, lang: str) -> list[TeamMemberOut]:
        rows = (
            await self.db.execute(
                select(TeamMember)
                .where(TeamMember.is_active.is_(True))
                .options(selectinload(TeamMember.translations))
                .order_by(TeamMember.position)
            )
        ).scalars().all()
        return [o for m in rows if (o := self._team_out(m, lang))]

    async def list_partners(self, lang: str, *, home_only: bool = False) -> list[PartnerOut]:
        stmt = (
            select(Partner)
            .where(Partner.is_active.is_(True))
            .options(
                selectinload(Partner.translations),
                selectinload(Partner.level).selectinload(PartnerLevel.translations),
            )
            .order_by(Partner.position)
        )
        if home_only:
            stmt = stmt.where(Partner.show_on_home.is_(True))
        rows = (await self.db.execute(stmt)).scalars().all()
        return [self._partner_out(p, lang) for p in rows]

    async def create_contact(self, body: ContactCreate, lang: str) -> ContactOut:
        if body.website:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "Requête rejetée", "code": "spam_detected"},
            )
        msg = ContactMessage(
            name=body.name,
            email=str(body.email).lower(),
            subject=body.subject,
            message=body.message,
            language_code=lang if lang in {"fr", "en"} else "fr",
        )
        self.db.add(msg)
        await self.db.commit()
        await self.db.refresh(msg)
        return ContactOut.model_validate(msg)

    async def list_articles(self, lang: str) -> list[ArticleOut]:
        rows = (
            await self.db.execute(
                select(Article)
                .where(published_filter(Article.status, Article.published_at))
                .options(selectinload(Article.translations), selectinload(Article.tags))
                .order_by(Article.published_at.desc())
            )
        ).scalars().all()
        return [a for art in rows if (a := self._article_out(art, lang))]

    async def get_article(self, slug: str, lang: str) -> ArticleOut:
        art = (
            await self.db.execute(
                select(Article)
                .where(
                    Article.slug == slug,
                    published_filter(Article.status, Article.published_at),
                )
                .options(selectinload(Article.translations), selectinload(Article.tags))
            )
        ).scalar_one_or_none()
        if art is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Article introuvable", "code": "article_not_found"},
            )
        out = self._article_out(art, lang)
        if out is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Traduction indisponible", "code": "translation_missing"},
            )
        return out

    # ----- admin pages -----

    async def list_pages_admin(self) -> list[PageAdminOut]:
        rows = (
            await self.db.execute(select(Page).options(selectinload(Page.translations)))
        ).scalars().all()
        return [
            PageAdminOut(
                id=p.id,
                slug=p.slug,
                status=p.status.value,
                published_at=p.published_at,
                cover_media_id=p.cover_media_id,
                translations=[
                    TranslationIn(
                        language_code=t.language_code,
                        title=t.title,
                        summary=t.summary,
                        body=t.body,
                        meta_title=t.meta_title,
                        meta_description=t.meta_description,
                    )
                    for t in p.translations
                ],
            )
            for p in rows
        ]

    async def upsert_page_translations(self, page: Page, translations: list[TranslationIn]) -> None:
        existing = {t.language_code: t for t in page.translations}
        for tr in translations:
            if tr.language_code in existing:
                row = existing[tr.language_code]
                row.title = tr.title
                row.summary = tr.summary
                row.body = tr.body
                row.meta_title = tr.meta_title
                row.meta_description = tr.meta_description
            else:
                page.translations.append(
                    PageTranslation(
                        language_code=tr.language_code,
                        title=tr.title,
                        summary=tr.summary,
                        body=tr.body,
                        meta_title=tr.meta_title,
                        meta_description=tr.meta_description,
                    )
                )

    async def create_page(self, body: PageCreate, auth: AuthContext) -> PageAdminOut:
        exists = (
            await self.db.execute(select(Page).where(Page.slug == body.slug))
        ).scalar_one_or_none()
        if exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"detail": "Slug déjà utilisé", "code": "slug_taken"},
            )
        page = Page(
            slug=body.slug,
            status=ContentStatus(body.status),
            published_at=body.published_at,
            cover_media_id=body.cover_media_id,
            created_by=auth.user.id,
            updated_by=auth.user.id,
        )
        self.db.add(page)
        await self.db.flush()
        await self.upsert_page_translations(page, body.translations)
        await log_activity(
            self.db,
            actor_id=auth.user.id,
            action="create",
            entity_type="page",
            entity_id=str(page.id),
        )
        await self.db.commit()
        return await self._page_admin(page.id)

    async def _page_admin(self, page_id: uuid.UUID) -> PageAdminOut:
        page = (
            await self.db.execute(
                select(Page).where(Page.id == page_id).options(selectinload(Page.translations))
            )
        ).scalar_one()
        return PageAdminOut(
            id=page.id,
            slug=page.slug,
            status=page.status.value,
            published_at=page.published_at,
            cover_media_id=page.cover_media_id,
            translations=[
                TranslationIn(
                    language_code=t.language_code,
                    title=t.title,
                    summary=t.summary,
                    body=t.body,
                    meta_title=t.meta_title,
                    meta_description=t.meta_description,
                )
                for t in page.translations
            ],
        )

    async def update_page(self, page_id: uuid.UUID, body: PageUpdate, auth: AuthContext) -> PageAdminOut:
        page = (
            await self.db.execute(
                select(Page).where(Page.id == page_id).options(selectinload(Page.translations))
            )
        ).scalar_one_or_none()
        if page is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Page introuvable", "code": "page_not_found"},
            )
        if body.status is not None:
            page.status = ContentStatus(body.status)
        if body.published_at is not None:
            page.published_at = body.published_at
        if body.cover_media_id is not None:
            page.cover_media_id = body.cover_media_id
        if body.translations is not None:
            await self.upsert_page_translations(page, body.translations)
        page.updated_by = auth.user.id
        await log_activity(
            self.db,
            actor_id=auth.user.id,
            action="update",
            entity_type="page",
            entity_id=str(page.id),
        )
        await self.db.commit()
        return await self._page_admin(page.id)

    async def publish_page(self, page_id: uuid.UUID, auth: AuthContext) -> PageAdminOut:
        return await self.update_page(
            page_id,
            PageUpdate(status="published", published_at=now_utc()),
            auth,
        )

    # ----- admin team -----

    async def create_team_member(self, body: TeamMemberCreate, auth: AuthContext) -> TeamMemberOut:
        member = TeamMember(
            full_name=body.full_name,
            team_group=body.team_group,
            linkedin_url=body.linkedin_url,
            position=body.position,
            photo_media_id=body.photo_media_id,
            user_id=body.user_id,
            is_active=body.is_active,
        )
        self.db.add(member)
        await self.db.flush()
        for tr in body.translations:
            self.db.add(
                TeamMemberTranslation(
                    team_member_id=member.id,
                    language_code=tr.language_code,
                    role_title=tr.role_title,
                    bio=tr.bio,
                )
            )
        await log_activity(
            self.db,
            actor_id=auth.user.id,
            action="create",
            entity_type="team_member",
            entity_id=str(member.id),
        )
        await self.db.commit()
        member = (
            await self.db.execute(
                select(TeamMember)
                .where(TeamMember.id == member.id)
                .options(selectinload(TeamMember.translations))
            )
        ).scalar_one()
        out = self._team_out(member, "fr")
        assert out is not None
        return out

    async def update_team_member(
        self, member_id: uuid.UUID, body: TeamMemberUpdate, auth: AuthContext
    ) -> TeamMemberOut:
        member = (
            await self.db.execute(
                select(TeamMember)
                .where(TeamMember.id == member_id)
                .options(selectinload(TeamMember.translations))
            )
        ).scalar_one_or_none()
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Membre d'équipe introuvable", "code": "team_not_found"},
            )
        for field in ("full_name", "team_group", "linkedin_url", "position", "photo_media_id", "is_active"):
            val = getattr(body, field)
            if val is not None:
                setattr(member, field, val)
        if body.translations is not None:
            by_lang = {t.language_code: t for t in member.translations}
            for tr in body.translations:
                if tr.language_code in by_lang:
                    by_lang[tr.language_code].role_title = tr.role_title
                    by_lang[tr.language_code].bio = tr.bio
                else:
                    member.translations.append(
                        TeamMemberTranslation(
                            language_code=tr.language_code,
                            role_title=tr.role_title,
                            bio=tr.bio,
                        )
                    )
        await log_activity(
            self.db,
            actor_id=auth.user.id,
            action="update",
            entity_type="team_member",
            entity_id=str(member.id),
        )
        await self.db.commit()
        out = self._team_out(member, "fr")
        assert out is not None
        return out

    # ----- admin partners -----

    async def create_partner(self, body: PartnerCreate, auth: AuthContext) -> PartnerOut:
        partner = Partner(
            slug=body.slug,
            name=body.name,
            website_url=body.website_url,
            logo_media_id=body.logo_media_id,
            level_id=body.level_id,
            show_on_home=body.show_on_home,
            position=body.position,
            is_active=body.is_active,
        )
        self.db.add(partner)
        await self.db.flush()
        if body.description_fr:
            self.db.add(
                PartnerTranslation(
                    partner_id=partner.id, language_code="fr", description=body.description_fr
                )
            )
        if body.description_en:
            self.db.add(
                PartnerTranslation(
                    partner_id=partner.id, language_code="en", description=body.description_en
                )
            )
        await log_activity(
            self.db,
            actor_id=auth.user.id,
            action="create",
            entity_type="partner",
            entity_id=str(partner.id),
        )
        await self.db.commit()
        partner = (
            await self.db.execute(
                select(Partner)
                .where(Partner.id == partner.id)
                .options(
                    selectinload(Partner.translations),
                    selectinload(Partner.level).selectinload(PartnerLevel.translations),
                )
            )
        ).scalar_one()
        return self._partner_out(partner, "fr")

    async def update_partner(
        self, partner_id: uuid.UUID, body: PartnerUpdate, auth: AuthContext
    ) -> PartnerOut:
        partner = (
            await self.db.execute(
                select(Partner)
                .where(Partner.id == partner_id)
                .options(
                    selectinload(Partner.translations),
                    selectinload(Partner.level).selectinload(PartnerLevel.translations),
                )
            )
        ).scalar_one_or_none()
        if partner is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Partenaire introuvable", "code": "partner_not_found"},
            )
        for field in (
            "name",
            "website_url",
            "logo_media_id",
            "level_id",
            "show_on_home",
            "position",
            "is_active",
        ):
            val = getattr(body, field)
            if val is not None:
                setattr(partner, field, val)
        by_lang = {t.language_code: t for t in partner.translations}
        for code, desc in (("fr", body.description_fr), ("en", body.description_en)):
            if desc is None:
                continue
            if code in by_lang:
                by_lang[code].description = desc
            else:
                partner.translations.append(
                    PartnerTranslation(language_code=code, description=desc)
                )
        await log_activity(
            self.db,
            actor_id=auth.user.id,
            action="update",
            entity_type="partner",
            entity_id=str(partner.id),
        )
        await self.db.commit()
        return self._partner_out(partner, "fr")

    # ----- admin articles -----

    async def create_article(self, body: ArticleCreate, auth: AuthContext) -> ArticleOut:
        article = Article(
            slug=body.slug,
            category_id=body.category_id,
            cover_media_id=body.cover_media_id,
            status=ContentStatus(body.status),
            published_at=body.published_at,
            author_id=auth.user.id,
            created_by=auth.user.id,
            updated_by=auth.user.id,
        )
        self.db.add(article)
        await self.db.flush()
        for tr in body.translations:
            self.db.add(
                ArticleTranslation(
                    article_id=article.id,
                    language_code=tr.language_code,
                    title=tr.title,
                    excerpt=tr.summary,
                    body=tr.body,
                    meta_title=tr.meta_title,
                    meta_description=tr.meta_description,
                )
            )
        for tag_id in body.tag_ids:
            self.db.add(ArticleTag(article_id=article.id, tag_id=tag_id))
        await log_activity(
            self.db,
            actor_id=auth.user.id,
            action="create",
            entity_type="article",
            entity_id=str(article.id),
        )
        await self.db.commit()
        article = (
            await self.db.execute(
                select(Article)
                .where(Article.id == article.id)
                .options(selectinload(Article.translations), selectinload(Article.tags))
            )
        ).scalar_one()
        out = self._article_out(article, "fr")
        assert out is not None
        return out

    async def update_article(
        self, article_id: uuid.UUID, body: ArticleUpdate, auth: AuthContext
    ) -> ArticleOut:
        article = (
            await self.db.execute(
                select(Article)
                .where(Article.id == article_id)
                .options(selectinload(Article.translations), selectinload(Article.tags))
            )
        ).scalar_one_or_none()
        if article is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Article introuvable", "code": "article_not_found"},
            )
        if body.status is not None:
            article.status = ContentStatus(body.status)
        if body.published_at is not None:
            article.published_at = body.published_at
        if body.category_id is not None:
            article.category_id = body.category_id
        if body.cover_media_id is not None:
            article.cover_media_id = body.cover_media_id
        if body.translations is not None:
            by_lang = {t.language_code: t for t in article.translations}
            for tr in body.translations:
                if tr.language_code in by_lang:
                    row = by_lang[tr.language_code]
                    row.title = tr.title
                    row.excerpt = tr.summary
                    row.body = tr.body
                    row.meta_title = tr.meta_title
                    row.meta_description = tr.meta_description
                else:
                    article.translations.append(
                        ArticleTranslation(
                            language_code=tr.language_code,
                            title=tr.title,
                            excerpt=tr.summary,
                            body=tr.body,
                            meta_title=tr.meta_title,
                            meta_description=tr.meta_description,
                        )
                    )
        if body.tag_ids is not None:
            old = (
                await self.db.execute(select(ArticleTag).where(ArticleTag.article_id == article.id))
            ).scalars().all()
            for row in old:
                await self.db.delete(row)
            for tag_id in body.tag_ids:
                self.db.add(ArticleTag(article_id=article.id, tag_id=tag_id))
        article.updated_by = auth.user.id
        await log_activity(
            self.db,
            actor_id=auth.user.id,
            action="update",
            entity_type="article",
            entity_id=str(article.id),
        )
        await self.db.commit()
        article = (
            await self.db.execute(
                select(Article)
                .where(Article.id == article_id)
                .options(selectinload(Article.translations), selectinload(Article.tags))
            )
        ).scalar_one()
        out = self._article_out(article, "fr")
        assert out is not None
        return out

    # ----- contact admin / key figures -----

    async def list_contacts(self) -> list[ContactOut]:
        rows = (
            await self.db.execute(
                select(ContactMessage).order_by(ContactMessage.created_at.desc())
            )
        ).scalars().all()
        return [ContactOut.model_validate(r) for r in rows]

    async def update_contact_status(
        self, message_id: uuid.UUID, status_value: str, auth: AuthContext
    ) -> ContactOut:
        msg = (
            await self.db.execute(select(ContactMessage).where(ContactMessage.id == message_id))
        ).scalar_one_or_none()
        if msg is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Message introuvable", "code": "contact_not_found"},
            )
        msg.status = status_value
        msg.handled_by = auth.user.id
        msg.handled_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(msg)
        return ContactOut.model_validate(msg)

    async def list_key_figures(self, lang: str) -> list[KeyFigureOut]:
        rows = (
            await self.db.execute(
                select(KeyFigure)
                .where(KeyFigure.edition_year.is_(None), KeyFigure.program_id.is_(None))
                .options(selectinload(KeyFigure.translations))
                .order_by(KeyFigure.position)
            )
        ).scalars().all()
        return [f for fig in rows if (f := self._figure_out(fig, lang))]

    async def update_key_figure(
        self, figure_id: int, body: KeyFigureUpdate, auth: AuthContext
    ) -> KeyFigureOut:
        fig = (
            await self.db.execute(
                select(KeyFigure)
                .where(KeyFigure.id == figure_id)
                .options(selectinload(KeyFigure.translations))
            )
        ).scalar_one_or_none()
        if fig is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Chiffre clé introuvable", "code": "key_figure_not_found"},
            )
        for field in ("value", "suffix", "show_on_home", "position", "is_active"):
            val = getattr(body, field)
            if val is not None:
                setattr(fig, field, val)
        fig.updated_by = auth.user.id
        by_lang = {t.language_code: t for t in fig.translations}
        for code, label in (("fr", body.label_fr), ("en", body.label_en)):
            if label is None:
                continue
            if code in by_lang:
                by_lang[code].label = label
            else:
                fig.translations.append(KeyFigureTranslation(language_code=code, label=label))
        await log_activity(
            self.db,
            actor_id=auth.user.id,
            action="update",
            entity_type="key_figure",
            entity_id=str(fig.id),
        )
        await self.db.commit()
        out = self._figure_out(fig, "fr")
        assert out is not None
        return out
