-- =====================================================================
-- ourtdev.com : schéma de base de données v0.2
-- Conforme au cahier des charges de refonte v1.0 (30/09/2026)
-- PostgreSQL 13 ou plus (testé sur 18) | Auteur : SADJINA Christ
--
-- Organisation en 8 blocs :
--   1. Socle (langues, comptes, rôles, communautés, médias, journal, paramètres, redirections)
--   2. Contenus institutionnels (pages, équipe, partenaires, blog, contact)
--   3. Festival (éditions, annonces)
--   4. Événements (événements, intervenants)
--   5. Programmes (initiatives, liens d'action, chiffres clés)
--   6. Membres et annuaire (profils, compétences, badges)
--   7. Projets open source
--   8. Ressources (dossiers et fichiers partagés)
--
-- Conventions :
--   - les contenus traduisibles ont une table <contenu>_translations (une ligne par langue)
--   - les contenus publiables ont un statut (draft, in_review, published, archived)
--     et une date de publication, qui permet la publication planifiée
--   - les fichiers (images, PDF) sont référencés via media_files
-- =====================================================================
BEGIN;

CREATE EXTENSION IF NOT EXISTS citext;

-- ---------------------------------------------------------------------
-- Types énumérés
-- ---------------------------------------------------------------------
CREATE TYPE user_status        AS ENUM ('pending', 'active', 'suspended', 'deleted');
CREATE TYPE content_status     AS ENUM ('draft', 'in_review', 'published', 'archived');
CREATE TYPE access_level       AS ENUM ('public', 'members');
CREATE TYPE review_status      AS ENUM ('pending', 'approved', 'rejected');
CREATE TYPE profile_visibility AS ENUM ('public', 'members', 'private');
CREATE TYPE member_status      AS ENUM ('student', 'professional', 'freelance', 'recruiter', 'other');
CREATE TYPE availability       AS ENUM ('available', 'open', 'unavailable');
CREATE TYPE event_type         AS ENUM ('meetup', 'workshop', 'conference', 'hackathon', 'training', 'festival', 'other');
CREATE TYPE event_format       AS ENUM ('onsite', 'online', 'hybrid');
CREATE TYPE program_type       AS ENUM ('training', 'hackathon', 'challenge', 'student_program', 'partnership', 'other');
CREATE TYPE program_status     AS ENUM ('upcoming', 'open', 'ongoing', 'finished');
CREATE TYPE project_stage      AS ENUM ('idea', 'in_progress', 'maintained', 'archived');
CREATE TYPE resource_type      AS ENUM ('slides', 'video', 'code', 'link', 'document');

-- Mise à jour automatique de updated_at (les triggers sont créés en fin de script)
CREATE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- =====================================================================
-- BLOC 1 : SOCLE
-- =====================================================================

-- Langues du site (fr par défaut, en ; d'autres pourront être ajoutées)
CREATE TABLE languages (
  code       varchar(5) PRIMARY KEY,          -- 'fr', 'en'
  name       text NOT NULL,
  is_default boolean NOT NULL DEFAULT false,
  is_active  boolean NOT NULL DEFAULT true,
  position   smallint NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX uq_languages_default ON languages (is_default) WHERE is_default;

-- Comptes utilisateurs (membres, leads, éditeurs, administrateurs)
CREATE TABLE users (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email              citext NOT NULL UNIQUE,
  password_hash      text,                    -- NULL si connexion uniquement via GitHub ou Google
  status             user_status NOT NULL DEFAULT 'pending',
  email_verified_at  timestamptz,
  approved_at        timestamptz,             -- validation de l'inscription par un administrateur
  approved_by        uuid REFERENCES users(id) ON DELETE SET NULL,
  preferred_language varchar(5) REFERENCES languages(code) ON DELETE SET NULL,
  last_login_at      timestamptz,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE oauth_accounts (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider         text NOT NULL CHECK (provider IN ('github', 'google')),
  provider_user_id text NOT NULL,
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (provider, provider_user_id),
  UNIQUE (user_id, provider)
);

-- Sessions : on stocke le hash du jeton, jamais le jeton lui-même
CREATE TABLE refresh_tokens (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash text NOT NULL UNIQUE,
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz,
  user_agent text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_refresh_tokens_user ON refresh_tokens (user_id);

-- Jetons à usage unique : vérification d'email, mot de passe oublié, lien de connexion
CREATE TABLE one_time_tokens (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  purpose    text NOT NULL CHECK (purpose IN ('verify_email', 'reset_password', 'magic_link')),
  token_hash text NOT NULL UNIQUE,
  expires_at timestamptz NOT NULL,
  used_at    timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_one_time_tokens_user ON one_time_tokens (user_id);

-- Double authentification (obligatoire pour les administrateurs)
CREATE TABLE user_mfa (
  user_id          uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  totp_secret_enc  text NOT NULL,             -- secret TOTP chiffré par l'API
  enabled_at       timestamptz,
  last_used_at     timestamptz
);

CREATE TABLE mfa_recovery_codes (
  id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id   uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  code_hash text NOT NULL,
  used_at   timestamptz
);
CREATE INDEX idx_mfa_recovery_user ON mfa_recovery_codes (user_id);

-- Communautés : antennes et groupes (périmètre d'action des Leads)
CREATE TABLE communities (
  id           serial PRIMARY KEY,
  slug         text NOT NULL UNIQUE,
  name         text NOT NULL,
  kind         text NOT NULL DEFAULT 'chapter' CHECK (kind IN ('chapter', 'group')),
  city         text,
  country_code char(2),
  is_active    boolean NOT NULL DEFAULT true,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);

-- Rôles et permissions
CREATE TABLE roles (
  id    smallserial PRIMARY KEY,
  code  text NOT NULL UNIQUE,                 -- member, lead, editor, admin
  label text NOT NULL
);

CREATE TABLE permissions (
  id          smallserial PRIMARY KEY,
  code        text NOT NULL UNIQUE,           -- ex. 'event.manage'
  description text
);

CREATE TABLE role_permissions (
  role_id       smallint NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  permission_id smallint NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
  PRIMARY KEY (role_id, permission_id)
);

-- Attribution des rôles ; community_id limite le rôle à une communauté (cas des Leads)
CREATE TABLE user_roles (
  id           bigserial PRIMARY KEY,
  user_id      uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role_id      smallint NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
  community_id int REFERENCES communities(id) ON DELETE CASCADE,
  granted_by   uuid REFERENCES users(id) ON DELETE SET NULL,
  granted_at   timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_user_roles ON user_roles (user_id, role_id, COALESCE(community_id, 0));

-- Médiathèque (images, PDF, présentations)
CREATE TABLE media_files (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  storage_key   text NOT NULL UNIQUE,         -- chemin dans le stockage objet
  url           text NOT NULL,
  original_name text,
  mime_type     text NOT NULL,
  size_bytes    bigint CHECK (size_bytes >= 0),
  width         int,
  height        int,
  uploaded_by   uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- Texte alternatif et légende par langue (accessibilité WCAG)
CREATE TABLE media_file_translations (
  media_id      uuid NOT NULL REFERENCES media_files(id) ON DELETE CASCADE,
  language_code varchar(5) NOT NULL REFERENCES languages(code) ON DELETE CASCADE,
  alt_text      text,
  caption       text,
  PRIMARY KEY (media_id, language_code)
);

-- Journal d'activité : qui a modifié quoi et quand
CREATE TABLE activity_logs (
  id          bigserial PRIMARY KEY,
  actor_id    uuid REFERENCES users(id) ON DELETE SET NULL,
  action      text NOT NULL,                  -- create, update, delete, publish, approve, reject, suspend...
  entity_type text NOT NULL,                  -- event, article, project, user...
  entity_id   text NOT NULL,
  changes     jsonb,                          -- détail des champs modifiés (sans données personnelles)
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_activity_entity ON activity_logs (entity_type, entity_id);
CREATE INDEX idx_activity_actor  ON activity_logs (actor_id, created_at DESC);

-- Paramètres du site modifiables depuis le back-office
CREATE TABLE site_settings (
  key         text PRIMARY KEY,
  value       jsonb NOT NULL,
  description text,
  updated_by  uuid REFERENCES users(id) ON DELETE SET NULL,
  updated_at  timestamptz NOT NULL DEFAULT now()
);

-- Redirections (anciennes URL, liens permanents vers les éditions du festival)
CREATE TABLE redirects (
  id          serial PRIMARY KEY,
  source_path text NOT NULL UNIQUE CHECK (source_path LIKE '/%'),
  target_url  text NOT NULL,
  status_code smallint NOT NULL DEFAULT 301 CHECK (status_code IN (301, 302)),
  is_active   boolean NOT NULL DEFAULT true,
  hit_count   int NOT NULL DEFAULT 0,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);


-- =====================================================================
-- BLOC 2 : CONTENUS INSTITUTIONNELS (module 1)
-- =====================================================================

-- Pages (accueil, à propos, contribuer, politique de confidentialité...)
CREATE TABLE pages (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug           text NOT NULL UNIQUE,
  cover_media_id uuid REFERENCES media_files(id) ON DELETE SET NULL,
  status         content_status NOT NULL DEFAULT 'draft',
  published_at   timestamptz,
  created_by     uuid REFERENCES users(id) ON DELETE SET NULL,
  updated_by     uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE page_translations (
  page_id          uuid NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
  language_code    varchar(5) NOT NULL REFERENCES languages(code) ON DELETE CASCADE,
  title            text NOT NULL,
  summary          text,
  body             text,                      -- contenu riche (HTML ou JSON de l'éditeur)
  meta_title       text,
  meta_description text,
  PRIMARY KEY (page_id, language_code)
);

-- Équipe et bureau (page À propos)
CREATE TABLE team_members (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        uuid REFERENCES users(id) ON DELETE SET NULL,
  full_name      text NOT NULL,
  photo_media_id uuid REFERENCES media_files(id) ON DELETE SET NULL,
  team_group     text NOT NULL DEFAULT 'team' CHECK (team_group IN ('board', 'team')),
  linkedin_url   text,
  position       smallint NOT NULL DEFAULT 0,
  is_active      boolean NOT NULL DEFAULT true,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE team_member_translations (
  team_member_id uuid NOT NULL REFERENCES team_members(id) ON DELETE CASCADE,
  language_code  varchar(5) NOT NULL REFERENCES languages(code) ON DELETE CASCADE,
  role_title     text NOT NULL,               -- ex. Président, Responsable communication
  bio            text,
  PRIMARY KEY (team_member_id, language_code)
);

-- Partenaires et niveaux de partenariat
CREATE TABLE partner_levels (
  id       smallserial PRIMARY KEY,
  code     text NOT NULL UNIQUE,
  position smallint NOT NULL DEFAULT 0
);

CREATE TABLE partner_level_translations (
  level_id      smallint NOT NULL REFERENCES partner_levels(id) ON DELETE CASCADE,
  language_code varchar(5) NOT NULL REFERENCES languages(code) ON DELETE CASCADE,
  name          text NOT NULL,
  PRIMARY KEY (level_id, language_code)
);

CREATE TABLE partners (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug          text NOT NULL UNIQUE,
  name          text NOT NULL,
  logo_media_id uuid REFERENCES media_files(id) ON DELETE SET NULL,
  website_url   text,
  level_id      smallint REFERENCES partner_levels(id) ON DELETE SET NULL,
  show_on_home  boolean NOT NULL DEFAULT false,
  position      smallint NOT NULL DEFAULT 0,
  is_active     boolean NOT NULL DEFAULT true,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE partner_translations (
  partner_id    uuid NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
  language_code varchar(5) NOT NULL REFERENCES languages(code) ON DELETE CASCADE,
  description   text,
  PRIMARY KEY (partner_id, language_code)
);

-- Blog et actualités
CREATE TABLE article_categories (
  id       serial PRIMARY KEY,
  slug     text NOT NULL UNIQUE,
  position smallint NOT NULL DEFAULT 0
);

CREATE TABLE article_category_translations (
  category_id   int NOT NULL REFERENCES article_categories(id) ON DELETE CASCADE,
  language_code varchar(5) NOT NULL REFERENCES languages(code) ON DELETE CASCADE,
  name          text NOT NULL,
  PRIMARY KEY (category_id, language_code)
);

-- Tags communs aux articles et aux ressources
CREATE TABLE tags (
  id   serial PRIMARY KEY,
  slug text NOT NULL UNIQUE,
  name text NOT NULL
);

CREATE TABLE articles (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug           text NOT NULL UNIQUE,
  category_id    int REFERENCES article_categories(id) ON DELETE SET NULL,
  author_id      uuid REFERENCES users(id) ON DELETE SET NULL,
  cover_media_id uuid REFERENCES media_files(id) ON DELETE SET NULL,
  status         content_status NOT NULL DEFAULT 'draft',
  published_at   timestamptz,
  created_by     uuid REFERENCES users(id) ON DELETE SET NULL,
  updated_by     uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_articles_published ON articles (status, published_at DESC);

CREATE TABLE article_translations (
  article_id       uuid NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  language_code    varchar(5) NOT NULL REFERENCES languages(code) ON DELETE CASCADE,
  title            text NOT NULL,
  excerpt          text,
  body             text,
  meta_title       text,
  meta_description text,
  PRIMARY KEY (article_id, language_code)
);

CREATE TABLE article_tags (
  article_id uuid NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  tag_id     int  NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
  PRIMARY KEY (article_id, tag_id)
);

-- Messages reçus via le formulaire de contact
CREATE TABLE contact_messages (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name          text NOT NULL,
  email         citext NOT NULL,
  subject       text,
  message       text NOT NULL,
  language_code varchar(5) REFERENCES languages(code) ON DELETE SET NULL,
  status        text NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'read', 'handled', 'spam')),
  handled_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  handled_at    timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_contact_status ON contact_messages (status, created_at DESC);


-- =====================================================================
-- BLOC 3 : FESTIVAL (module 4)
-- =====================================================================

-- Une ligne par édition ; target_url est la destination du lien permanent /festival/<année>,
-- modifiable depuis le back-office sans toucher au code
CREATE TABLE festival_editions (
  year           smallint PRIMARY KEY CHECK (year >= 2020),
  starts_on      date,
  ends_on        date,
  city           text,
  venue          text,
  target_url     text,
  logo_media_id  uuid REFERENCES media_files(id) ON DELETE SET NULL,
  cover_media_id uuid REFERENCES media_files(id) ON DELETE SET NULL,
  is_current     boolean NOT NULL DEFAULT false,
  status         content_status NOT NULL DEFAULT 'draft',
  published_at   timestamptz,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CHECK (ends_on IS NULL OR starts_on IS NULL OR ends_on >= starts_on)
);
-- Une seule édition en cours à la fois
CREATE UNIQUE INDEX uq_festival_current ON festival_editions (is_current) WHERE is_current;

CREATE TABLE festival_edition_translations (
  edition_year  smallint NOT NULL REFERENCES festival_editions(year) ON DELETE CASCADE,
  language_code varchar(5) NOT NULL REFERENCES languages(code) ON DELETE CASCADE,
  theme         text,
  summary       text,
  description   text,
  PRIMARY KEY (edition_year, language_code)
);

-- Bandeaux d'annonce sur l'accueil (inscriptions, appel à speakers, billetterie)
CREATE TABLE announcements (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  edition_year smallint REFERENCES festival_editions(year) ON DELETE CASCADE,
  kind         text NOT NULL DEFAULT 'other'
               CHECK (kind IN ('registration', 'call_for_speakers', 'ticketing', 'other')),
  cta_url      text,
  starts_at    timestamptz NOT NULL,
  ends_at      timestamptz,
  is_active    boolean NOT NULL DEFAULT true,
  position     smallint NOT NULL DEFAULT 0,
  created_by   uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  CHECK (ends_at IS NULL OR ends_at > starts_at)
);
CREATE INDEX idx_announcements_active ON announcements (is_active, starts_at);

CREATE TABLE announcement_translations (
  announcement_id uuid NOT NULL REFERENCES announcements(id) ON DELETE CASCADE,
  language_code   varchar(5) NOT NULL REFERENCES languages(code) ON DELETE CASCADE,
  message         text NOT NULL,
  cta_label       text,
  PRIMARY KEY (announcement_id, language_code)
);


-- =====================================================================
-- BLOC 4 : ÉVÉNEMENTS ET INTERVENANTS (module 3)
-- =====================================================================

CREATE TABLE events (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug               text NOT NULL UNIQUE,
  type               event_type NOT NULL,
  format             event_format NOT NULL DEFAULT 'onsite',
  starts_at          timestamptz NOT NULL,
  ends_at            timestamptz,
  timezone           text NOT NULL DEFAULT 'Africa/Lome',
  venue              text,
  city               text,
  country_code       char(2),
  online_url         text,
  registration_url   text,
  replay_url         text,
  cover_media_id     uuid REFERENCES media_files(id) ON DELETE SET NULL,
  community_id       int REFERENCES communities(id) ON DELETE SET NULL,
  edition_year       smallint REFERENCES festival_editions(year) ON DELETE SET NULL,
  show_in_timeline   boolean NOT NULL DEFAULT false,   -- frise chronologique de TDEV
  participants_count int CHECK (participants_count >= 0),
  sessions_count     int CHECK (sessions_count >= 0),
  show_stats         boolean NOT NULL DEFAULT false,
  status             content_status NOT NULL DEFAULT 'draft',
  published_at       timestamptz,
  created_by         uuid REFERENCES users(id) ON DELETE SET NULL,
  updated_by         uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  CHECK (ends_at IS NULL OR ends_at >= starts_at)
);
CREATE INDEX idx_events_listing   ON events (status, starts_at DESC);
CREATE INDEX idx_events_filters   ON events (type, format, city);
CREATE INDEX idx_events_community ON events (community_id);

CREATE TABLE event_translations (
  event_id         uuid NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  language_code    varchar(5) NOT NULL REFERENCES languages(code) ON DELETE CASCADE,
  title            text NOT NULL,
  summary          text,
  description      text,
  meta_title       text,
  meta_description text,
  PRIMARY KEY (event_id, language_code)
);

-- Galerie : photos (médiathèque) et vidéos (lien externe)
CREATE TABLE event_media (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id   uuid NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  kind       text NOT NULL CHECK (kind IN ('photo', 'video')),
  media_id   uuid REFERENCES media_files(id) ON DELETE CASCADE,
  url        text,
  position   smallint NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (media_id IS NOT NULL OR url IS NOT NULL)
);
CREATE INDEX idx_event_media_event ON event_media (event_id, position);

-- Intervenants : pas forcément membres de la plateforme
CREATE TABLE speakers (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        uuid UNIQUE REFERENCES users(id) ON DELETE SET NULL,
  full_name      text NOT NULL,
  photo_media_id uuid REFERENCES media_files(id) ON DELETE SET NULL,
  organization   text,
  linkedin_url   text,
  github_url     text,
  website_url    text,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE speaker_translations (
  speaker_id    uuid NOT NULL REFERENCES speakers(id) ON DELETE CASCADE,
  language_code varchar(5) NOT NULL REFERENCES languages(code) ON DELETE CASCADE,
  job_title     text,
  bio           text,
  PRIMARY KEY (speaker_id, language_code)
);

CREATE TABLE event_speakers (
  event_id   uuid NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  speaker_id uuid NOT NULL REFERENCES speakers(id) ON DELETE CASCADE,
  role       text NOT NULL DEFAULT 'speaker' CHECK (role IN ('speaker', 'panelist', 'moderator', 'trainer')),
  position   smallint NOT NULL DEFAULT 0,
  PRIMARY KEY (event_id, speaker_id)
);

CREATE TABLE event_partners (
  event_id   uuid NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  partner_id uuid NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
  PRIMARY KEY (event_id, partner_id)
);

-- Membres ayant participé (tableau de bord membre : mes événements)
CREATE TABLE event_participants (
  event_id      uuid NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  user_id       uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role          text NOT NULL DEFAULT 'attendee' CHECK (role IN ('attendee', 'volunteer', 'organizer')),
  registered_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (event_id, user_id)
);
CREATE INDEX idx_event_participants_user ON event_participants (user_id);


-- =====================================================================
-- BLOC 5 : PROGRAMMES ET CHIFFRES CLÉS (module 7)
-- =====================================================================

CREATE TABLE programs (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug                 text NOT NULL UNIQUE,
  type                 program_type NOT NULL,
  program_status       program_status NOT NULL DEFAULT 'upcoming',
  starts_on            date,
  ends_on              date,
  application_deadline date,
  is_featured          boolean NOT NULL DEFAULT false,   -- mise en avant sur l'accueil
  cover_media_id       uuid REFERENCES media_files(id) ON DELETE SET NULL,
  community_id         int REFERENCES communities(id) ON DELETE SET NULL,
  position             smallint NOT NULL DEFAULT 0,
  status               content_status NOT NULL DEFAULT 'draft',
  published_at         timestamptz,
  created_by           uuid REFERENCES users(id) ON DELETE SET NULL,
  updated_by           uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now(),
  CHECK (ends_on IS NULL OR starts_on IS NULL OR ends_on >= starts_on)
);
CREATE INDEX idx_programs_listing ON programs (status, program_status);

CREATE TABLE program_translations (
  program_id      uuid NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
  language_code   varchar(5) NOT NULL REFERENCES languages(code) ON DELETE CASCADE,
  title           text NOT NULL,
  summary         text,
  objective       text,
  target_audience text,
  schedule        text,
  conditions      text,
  PRIMARY KEY (program_id, language_code)
);

-- Boutons d'action paramétrables (postuler, s'inscrire, en savoir plus, site dédié)
CREATE TABLE program_links (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  program_id uuid NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
  kind       text NOT NULL DEFAULT 'learn_more'
             CHECK (kind IN ('apply', 'register', 'learn_more', 'website', 'other')),
  url        text NOT NULL,
  is_primary boolean NOT NULL DEFAULT false,
  position   smallint NOT NULL DEFAULT 0
);
CREATE INDEX idx_program_links_program ON program_links (program_id, position);

CREATE TABLE program_link_translations (
  link_id       uuid NOT NULL REFERENCES program_links(id) ON DELETE CASCADE,
  language_code varchar(5) NOT NULL REFERENCES languages(code) ON DELETE CASCADE,
  label         text NOT NULL,
  PRIMARY KEY (link_id, language_code)
);

CREATE TABLE program_partners (
  program_id uuid NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
  partner_id uuid NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
  PRIMARY KEY (program_id, partner_id)
);

-- Chiffres clés modifiables depuis le back-office :
-- globaux (accueil, impact), par édition du festival ou par programme
CREATE TABLE key_figures (
  id           serial PRIMARY KEY,
  code         text NOT NULL,
  value        numeric NOT NULL,
  suffix       text,                          -- ex. '+', '%'
  edition_year smallint REFERENCES festival_editions(year) ON DELETE CASCADE,
  program_id   uuid REFERENCES programs(id) ON DELETE CASCADE,
  show_on_home boolean NOT NULL DEFAULT false,
  position     smallint NOT NULL DEFAULT 0,
  is_active    boolean NOT NULL DEFAULT true,
  updated_by   uuid REFERENCES users(id) ON DELETE SET NULL,
  updated_at   timestamptz NOT NULL DEFAULT now(),
  CHECK (edition_year IS NULL OR program_id IS NULL)   -- rattaché à une édition OU un programme, pas les deux
);
CREATE UNIQUE INDEX uq_key_figures_code
  ON key_figures (code, COALESCE(edition_year, 0), COALESCE(program_id, '00000000-0000-0000-0000-000000000000'));

CREATE TABLE key_figure_translations (
  key_figure_id int NOT NULL REFERENCES key_figures(id) ON DELETE CASCADE,
  language_code varchar(5) NOT NULL REFERENCES languages(code) ON DELETE CASCADE,
  label         text NOT NULL,
  PRIMARY KEY (key_figure_id, language_code)
);


-- =====================================================================
-- BLOC 6 : MEMBRES ET ANNUAIRE (module 2)
-- =====================================================================

-- Profil public : pseudonyme et informations que le membre choisit de montrer
CREATE TABLE member_profiles (
  user_id              uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  handle               text NOT NULL UNIQUE CHECK (handle ~ '^[a-z0-9_-]{3,30}$'),
  display_name         text NOT NULL,
  title                text,                  -- ex. Développeur Flutter
  bio                  text,
  city                 text,
  country_code         char(2),
  avatar_media_id      uuid REFERENCES media_files(id) ON DELETE SET NULL,
  member_status        member_status,
  availability         availability NOT NULL DEFAULT 'unavailable',
  years_experience     smallint CHECK (years_experience BETWEEN 0 AND 60),
  github_url           text,
  linkedin_url         text,
  portfolio_url        text,
  -- Consentement et contrôle de la visibilité par le membre
  visibility           profile_visibility NOT NULL DEFAULT 'members',
  listed_in_directory  boolean NOT NULL DEFAULT false,
  directory_consent_at timestamptz,
  show_location        boolean NOT NULL DEFAULT true,
  show_links           boolean NOT NULL DEFAULT true,
  allow_contact        boolean NOT NULL DEFAULT false,  -- contact via formulaire, sans exposer l'email
  -- Modération
  hidden_at            timestamptz,
  hidden_by            uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now(),
  CHECK (NOT listed_in_directory OR directory_consent_at IS NOT NULL)
);
CREATE INDEX idx_member_profiles_directory
  ON member_profiles (country_code, city, member_status) WHERE listed_in_directory AND hidden_at IS NULL;

-- Données personnelles isolées : jamais exposées par les pages publiques
CREATE TABLE member_pii (
  user_id    uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  first_name text,
  last_name  text,
  phone      text,
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Compétences (servent aussi aux projets)
CREATE TABLE technologies (
  id       serial PRIMARY KEY,
  slug     text NOT NULL UNIQUE,
  name     citext NOT NULL UNIQUE,
  category text                               -- langage, framework, design, data...
);

CREATE TABLE member_technologies (
  user_id       uuid NOT NULL REFERENCES member_profiles(user_id) ON DELETE CASCADE,
  technology_id int  NOT NULL REFERENCES technologies(id) ON DELETE CASCADE,
  level         smallint CHECK (level BETWEEN 1 AND 5),
  PRIMARY KEY (user_id, technology_id)
);
CREATE INDEX idx_member_tech_technology ON member_technologies (technology_id);

-- Badges affichés sur le profil (sans droits associés)
CREATE TABLE badges (
  id            smallserial PRIMARY KEY,
  code          text NOT NULL UNIQUE,         -- lead, contributor, speaker, festival_alumni
  icon_media_id uuid REFERENCES media_files(id) ON DELETE SET NULL,
  position      smallint NOT NULL DEFAULT 0
);

CREATE TABLE badge_translations (
  badge_id      smallint NOT NULL REFERENCES badges(id) ON DELETE CASCADE,
  language_code varchar(5) NOT NULL REFERENCES languages(code) ON DELETE CASCADE,
  name          text NOT NULL,
  description   text,
  PRIMARY KEY (badge_id, language_code)
);

CREATE TABLE member_badges (
  user_id      uuid NOT NULL REFERENCES member_profiles(user_id) ON DELETE CASCADE,
  badge_id     smallint NOT NULL REFERENCES badges(id) ON DELETE CASCADE,
  edition_year smallint REFERENCES festival_editions(year) ON DELETE SET NULL,
  awarded_by   uuid REFERENCES users(id) ON DELETE SET NULL,
  awarded_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, badge_id)
);

-- Messages envoyés à un membre via la plateforme (son email n'est jamais montré)
CREATE TABLE member_messages (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  recipient_id   uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  sender_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  sender_name    text NOT NULL,
  sender_email   citext NOT NULL,
  subject        text,
  message        text NOT NULL,
  status         text NOT NULL DEFAULT 'sent' CHECK (status IN ('sent', 'spam')),
  created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_member_messages_recipient ON member_messages (recipient_id, created_at DESC);


-- =====================================================================
-- BLOC 7 : PROJETS OPEN SOURCE (module 5)
-- =====================================================================

CREATE TABLE project_categories (
  id       serial PRIMARY KEY,
  slug     text NOT NULL UNIQUE,
  position smallint NOT NULL DEFAULT 0
);

CREATE TABLE project_category_translations (
  category_id   int NOT NULL REFERENCES project_categories(id) ON DELETE CASCADE,
  language_code varchar(5) NOT NULL REFERENCES languages(code) ON DELETE CASCADE,
  name          text NOT NULL,
  PRIMARY KEY (category_id, language_code)
);

-- stage : avancement du projet ; review_status : validation de la soumission par un éditeur
CREATE TABLE projects (
  id                        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug                      text NOT NULL UNIQUE,
  name                      text NOT NULL,
  category_id               int REFERENCES project_categories(id) ON DELETE SET NULL,
  stage                     project_stage NOT NULL DEFAULT 'idea',
  license                   text,               -- identifiant SPDX : MIT, Apache-2.0, GPL-3.0...
  repo_url                  text,
  demo_url                  text,
  website_url               text,
  logo_media_id             uuid REFERENCES media_files(id) ON DELETE SET NULL,
  is_featured               boolean NOT NULL DEFAULT false,
  review_status             review_status NOT NULL DEFAULT 'pending',
  rejection_reason          text,
  submitted_by              uuid REFERENCES users(id) ON DELETE SET NULL,
  reviewed_by               uuid REFERENCES users(id) ON DELETE SET NULL,
  reviewed_at               timestamptz,
  -- Données GitHub mises à jour automatiquement
  github_full_name          text UNIQUE,        -- 'owner/repo'
  github_stars              int,
  github_forks              int,
  github_contributors_count int,
  github_last_commit_at     timestamptz,
  github_synced_at          timestamptz,
  created_at                timestamptz NOT NULL DEFAULT now(),
  updated_at                timestamptz NOT NULL DEFAULT now(),
  CHECK (review_status <> 'rejected' OR rejection_reason IS NOT NULL)
);
CREATE INDEX idx_projects_listing ON projects (review_status, stage, created_at DESC);

CREATE TABLE project_translations (
  project_id    uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  language_code varchar(5) NOT NULL REFERENCES languages(code) ON DELETE CASCADE,
  summary       text NOT NULL,
  description   text,
  PRIMARY KEY (project_id, language_code)
);

CREATE TABLE project_technologies (
  project_id    uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  technology_id int  NOT NULL REFERENCES technologies(id) ON DELETE CASCADE,
  PRIMARY KEY (project_id, technology_id)
);
CREATE INDEX idx_project_tech_technology ON project_technologies (technology_id);

-- Contributeurs liés à leur profil membre
CREATE TABLE project_contributors (
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role       text NOT NULL DEFAULT 'contributor' CHECK (role IN ('maintainer', 'contributor')),
  joined_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, user_id)
);
CREATE INDEX idx_project_contributors_user ON project_contributors (user_id);


-- =====================================================================
-- BLOC 8 : RESSOURCES (module 6)
-- =====================================================================

-- Dossiers : un par événement ou session (ex. Festival 2026 / Atelier IA), sous-dossiers possibles
CREATE TABLE resource_folders (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  parent_id    uuid REFERENCES resource_folders(id) ON DELETE CASCADE,
  slug         text NOT NULL,
  event_id     uuid REFERENCES events(id) ON DELETE SET NULL,
  program_id   uuid REFERENCES programs(id) ON DELETE SET NULL,
  edition_year smallint REFERENCES festival_editions(year) ON DELETE SET NULL,
  community_id int REFERENCES communities(id) ON DELETE SET NULL,
  access_level access_level NOT NULL DEFAULT 'public',
  position     smallint NOT NULL DEFAULT 0,
  status       content_status NOT NULL DEFAULT 'draft',
  published_at timestamptz,
  created_by   uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  CHECK (parent_id IS NULL OR parent_id <> id)
);
CREATE UNIQUE INDEX uq_resource_folders_slug
  ON resource_folders (COALESCE(parent_id, '00000000-0000-0000-0000-000000000000'), slug);
CREATE INDEX idx_resource_folders_event ON resource_folders (event_id);

CREATE TABLE resource_folder_translations (
  folder_id     uuid NOT NULL REFERENCES resource_folders(id) ON DELETE CASCADE,
  language_code varchar(5) NOT NULL REFERENCES languages(code) ON DELETE CASCADE,
  name          text NOT NULL,
  description   text,
  PRIMARY KEY (folder_id, language_code)
);

-- Une ressource est soit un fichier de la médiathèque, soit un lien (YouTube, Drive, dépôt)
CREATE TABLE resources (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  folder_id      uuid NOT NULL REFERENCES resource_folders(id) ON DELETE CASCADE,
  type           resource_type NOT NULL,
  media_id       uuid REFERENCES media_files(id) ON DELETE SET NULL,
  url            text,
  speaker_id     uuid REFERENCES speakers(id) ON DELETE SET NULL,
  access_level   access_level NOT NULL DEFAULT 'public',
  view_count     int NOT NULL DEFAULT 0,
  download_count int NOT NULL DEFAULT 0,
  position       smallint NOT NULL DEFAULT 0,
  status         content_status NOT NULL DEFAULT 'draft',
  published_at   timestamptz,
  created_by     uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CHECK (media_id IS NOT NULL OR url IS NOT NULL)
);
CREATE INDEX idx_resources_folder  ON resources (folder_id, position);
CREATE INDEX idx_resources_filters ON resources (type, access_level, status);

CREATE TABLE resource_translations (
  resource_id   uuid NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
  language_code varchar(5) NOT NULL REFERENCES languages(code) ON DELETE CASCADE,
  title         text NOT NULL,
  description   text,
  PRIMARY KEY (resource_id, language_code)
);

CREATE TABLE resource_tags (
  resource_id uuid NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
  tag_id      int  NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
  PRIMARY KEY (resource_id, tag_id)
);


-- =====================================================================
-- Triggers updated_at sur toutes les tables qui ont la colonne
-- =====================================================================
DO $$
DECLARE t text;
BEGIN
  FOR t IN
    SELECT table_name FROM information_schema.columns
    WHERE table_schema = 'public' AND column_name = 'updated_at'
  LOOP
    EXECUTE format(
      'CREATE TRIGGER trg_%s_updated_at BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION set_updated_at()',
      t, t);
  END LOOP;
END $$;

COMMIT;
