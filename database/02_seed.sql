-- =====================================================================
-- ourtdev.com : données de référence v0.2
-- À exécuter une seule fois, après 01_schema.sql
-- =====================================================================
BEGIN;

-- Langues
INSERT INTO languages (code, name, is_default, position) VALUES
  ('fr', 'Français', true,  1),
  ('en', 'English',  false, 2);

-- Rôles (cahier des charges, section 4)
INSERT INTO roles (code, label) VALUES
  ('member', 'Membre'),
  ('lead',   'Lead de communauté'),
  ('editor', 'Éditeur'),
  ('admin',  'Administrateur');

-- Permissions
INSERT INTO permissions (code, description) VALUES
  ('profile.edit_own',           'Modifier son propre profil'),
  ('resource.read_members',      'Accéder aux ressources réservées aux membres'),
  ('project.submit',             'Soumettre un projet open source'),
  ('event.propose',              'Proposer un événement pour sa communauté'),
  ('resource.manage_community',  'Ajouter des ressources pour sa communauté'),
  ('event.manage',               'Gérer tous les événements'),
  ('article.manage',             'Gérer les articles du blog'),
  ('resource.manage',            'Gérer toutes les ressources'),
  ('program.manage',             'Gérer les programmes et initiatives'),
  ('page.manage',                'Gérer les pages institutionnelles'),
  ('partner.manage',             'Gérer les partenaires'),
  ('festival.manage',            'Gérer les éditions du festival et les annonces'),
  ('key_figure.manage',          'Modifier les chiffres clés'),
  ('media.manage',               'Gérer la médiathèque'),
  ('project.review',             'Valider ou refuser les projets soumis'),
  ('member.approve',             'Valider les inscriptions des membres'),
  ('member.moderate',            'Masquer un profil, suspendre un compte'),
  ('contact.read',               'Lire les messages du formulaire de contact'),
  ('member.export',              'Exporter la base des membres en CSV'),
  ('pii.read',                   'Lire les données personnelles (nom, téléphone)'),
  ('user.manage',                'Gérer les comptes utilisateurs'),
  ('role.assign',                'Attribuer les rôles'),
  ('settings.manage',            'Modifier les paramètres du site et les redirections'),
  ('activity_log.read',          'Consulter le journal d''activité');

-- Droits par rôle : chaque rôle reprend ceux du rôle précédent
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON
     (r.code IN ('member', 'lead', 'editor')
       AND p.code IN ('profile.edit_own', 'resource.read_members', 'project.submit'))
  OR (r.code IN ('lead', 'editor')
       AND p.code IN ('event.propose', 'resource.manage_community'))
  OR (r.code = 'editor'
       AND p.code IN ('event.manage', 'article.manage', 'resource.manage', 'program.manage',
                      'page.manage', 'partner.manage', 'festival.manage', 'key_figure.manage',
                      'media.manage', 'project.review', 'member.approve', 'member.moderate',
                      'contact.read'))
  OR (r.code = 'admin');

-- Badges (cahier des charges, exigence 2.5)
INSERT INTO badges (code, position) VALUES
  ('lead', 1), ('contributor', 2), ('speaker', 3), ('festival_alumni', 4);

INSERT INTO badge_translations (badge_id, language_code, name)
SELECT b.id, t.lang, t.name
FROM badges b
JOIN (VALUES
  ('lead', 'fr', 'Lead'),                     ('lead', 'en', 'Lead'),
  ('contributor', 'fr', 'Contributeur'),      ('contributor', 'en', 'Contributor'),
  ('speaker', 'fr', 'Speaker'),               ('speaker', 'en', 'Speaker'),
  ('festival_alumni', 'fr', 'Alumni Festival'), ('festival_alumni', 'en', 'Festival alumni')
) AS t(code, lang, name) ON t.code = b.code;

-- Niveaux de partenariat (à ajuster selon la grille TDEV)
INSERT INTO partner_levels (code, position) VALUES
  ('main', 1), ('gold', 2), ('silver', 3), ('community', 4);

INSERT INTO partner_level_translations (level_id, language_code, name)
SELECT l.id, t.lang, t.name
FROM partner_levels l
JOIN (VALUES
  ('main', 'fr', 'Partenaire principal'),    ('main', 'en', 'Main partner'),
  ('gold', 'fr', 'Partenaire Or'),           ('gold', 'en', 'Gold partner'),
  ('silver', 'fr', 'Partenaire Argent'),     ('silver', 'en', 'Silver partner'),
  ('community', 'fr', 'Partenaire communautaire'), ('community', 'en', 'Community partner')
) AS t(code, lang, name) ON t.code = l.code;

-- Pages institutionnelles de base (en brouillon, contenu à rédiger)
INSERT INTO pages (slug) VALUES
  ('accueil'), ('a-propos'), ('contact'), ('contribuer'), ('politique-de-confidentialite');

INSERT INTO page_translations (page_id, language_code, title)
SELECT p.id, t.lang, t.title
FROM pages p
JOIN (VALUES
  ('accueil', 'fr', 'Accueil'),                    ('accueil', 'en', 'Home'),
  ('a-propos', 'fr', 'À propos'),                  ('a-propos', 'en', 'About'),
  ('contact', 'fr', 'Contact'),                    ('contact', 'en', 'Contact'),
  ('contribuer', 'fr', 'Contribuer'),              ('contribuer', 'en', 'Contribute'),
  ('politique-de-confidentialite', 'fr', 'Politique de confidentialité'),
  ('politique-de-confidentialite', 'en', 'Privacy policy')
) AS t(slug, lang, title) ON t.slug = p.slug;

-- Chiffres clés de l'accueil (valeurs à confirmer par le bureau TDEV)
INSERT INTO key_figures (code, value, suffix, show_on_home, position) VALUES
  ('members',   2000, '+', true, 1),
  ('events',      30, '+', true, 2);

INSERT INTO key_figure_translations (key_figure_id, language_code, label)
SELECT k.id, t.lang, t.label
FROM key_figures k
JOIN (VALUES
  ('members', 'fr', 'membres actifs'),   ('members', 'en', 'active members'),
  ('events', 'fr', 'rencontres'),        ('events', 'en', 'events')
) AS t(code, lang, label) ON t.code = k.code AND k.edition_year IS NULL AND k.program_id IS NULL;

-- Paramètres du site
INSERT INTO site_settings (key, value, description) VALUES
  ('site_name',          '"TDEV"',                 'Nom affiché du site'),
  ('default_language',   '"fr"',                   'Langue par défaut'),
  ('member_validation',  '"email"',                'Validation des inscriptions : email, admin ou both'),
  ('social_links',       '{}',                     'Liens vers les réseaux sociaux (Telegram, LinkedIn, X...)');

COMMIT;
