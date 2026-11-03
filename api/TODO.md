# TODO API — ourtdev.com

Checklist de progression. Cocher au fur et à mesure (`[ ]` → `[x]`).

Priorités CDC : **M** = indispensable · **S** = important · **C** = souhaitable (plus tard).

Ordre de travail recommandé :
1. Socle
2. Lot 1 → modules 1, 3, 4, 7
3. Lot 2 → modules 2, 5, 6

Voir aussi [`rules.md`](rules.md).

---

## 0. Socle (obligatoire avant les modules)

Sans ça, auth et back-office ne tiennent pas.

- [x] Scaffold FastAPI (monolithe modulaire) + `pyproject.toml` / deps
- [x] Config `.env` + `.env.example` (`DATABASE_URL`, secrets JWT, etc.)
- [x] Connexion PostgreSQL async (SQLAlchemy 2 + asyncpg)
- [x] Healthcheck `GET /api/v1/health`
- [x] Modèles SQLAlchemy alignés sur `database/01_schema.sql` (bloc 1 socle)
- [x] Erreurs JSON homogènes + pagination + helper i18n (fallback `fr`)
- [x] Auth : register / login email + mot de passe
- [x] Auth : JWT access + refresh (hashés en base)
- [x] Auth : OAuth GitHub + Google **(M)**
- [x] Auth : vérification email / reset password (`one_time_tokens`)
- [x] MFA TOTP obligatoire pour les admins **(M)**
- [x] RBAC : dépendance `require_permission("…")` sur les 24 permissions seedées
- [x] Journal `activity_logs` (actions back-office, sans PII) **(S)**
- [x] `site_settings` lisibles / modifiables (admin) **(M)**
- [x] Module `media` : upload + enregistrement `media_files` **(M)**
- [x] OpenAPI documenté (tags par module) pour le front Next.js
- [x] Tests de base (health + auth)

---

## Module 1 — Pages institutionnelles et accueil

Tables : `pages`, `team_members`, `partners`, `partner_levels`, `articles`, `article_categories`, `tags`, `contact_messages`, `key_figures`

### Important (M)

- [x] Lecture publique page d’accueil (chiffres clés, prochains events, dernières actus — agrégation)
- [x] CRUD / lecture pages (`accueil`, `a-propos`, `contact`, etc.) bilingue
- [x] Page À propos : équipe / bureau (`team_members`)
- [x] Partenaires : liste + niveaux + logos **(M)**
- [x] Contact : `POST` message + anti-spam (captcha / rate limit) **(M)**
- [x] i18n FR/EN sur tous les contenus de ce module **(M)**

### Important ensuite (S)

- [x] Blog / actualités : liste, fiche, catégories, tags **(S)**
- [x] Admin : workflow `draft → in_review → published` + `published_at` **(S)**

### Plus tard (C)

- [ ] —

---

## Module 2 — Espace membres et annuaire

Tables : `member_profiles`, `member_pii`, `technologies`, `member_technologies`, `badges`, `member_badges`, `member_messages`

### Important (M)

- [ ] Inscription + validation selon `site_settings.member_validation` (`email` / `admin` / `both`)
- [ ] Profil membre : handle, photo, ville/pays, titre, bio, compétences, liens, statut
- [ ] Consentement annuaire (`listed_in_directory` + `directory_consent_at`)
- [ ] Annuaire public : recherche + filtres (compétence, ville, pays, statut)
- [ ] Respect visibilité : `visibility`, `show_location`, `show_links`, `hidden_at`
- [ ] **Jamais** exposer `member_pii` ni email sur routes publiques

### Important ensuite (S)

- [ ] Badges (Lead, contributeur, speaker, alumni) **(S)**
- [ ] Dashboard membre : mes events / ressources / projets **(S)**
- [ ] Export CSV membres (admin, `member.export`) **(S)**

### Plus tard (C)

- [ ] Contact membre via formulaire sans exposer l’email (`member_messages`) **(C)**

---

## Module 3 — Événements et meetups

Tables : `events`, `event_translations`, `event_media`, `speakers`, `event_speakers`, `event_partners`, `event_participants`

### Important (M)

- [ ] Liste événements à venir / passés
- [ ] Filtres : type, année, ville, onsite/online/hybrid
- [ ] Fiche événement : titre, date, lieu, description, speakers, partenaires, galerie, replay, inscription
- [ ] Lien automatique événement → dossier ressources (module 6)
- [ ] Visibilité : `published` + `published_at <= now()`
- [ ] Lead : proposer un event limité à sa `community_id` (`event.propose`)

### Important ensuite (S)

- [ ] Frise chronologique (`show_in_timeline`) **(S)**
- [ ] Export / lien calendrier `.ics` **(S)**

### Plus tard (C)

- [ ] Stats participants / sessions (`show_stats`) **(C)**

---

## Module 4 — Festival (éditions et redirections)

Tables : `festival_editions`, `announcements`, `redirects`

### Important (M)

- [ ] Page / liste Festival : édition en cours (`is_current`)
- [ ] Archive des éditions (année, thème, dates, chiffres, lien)
- [ ] `target_url` par édition modifiable (back-office, sans toucher au code)
- [ ] Résolution `/festival/{année}` → `target_url`
- [ ] Annonces actives pour bandeau accueil (inscriptions, speakers, billetterie)

### Important ensuite (S)

- [ ] Redirections 301 (`redirects`) quand un lien d’édition change **(S)**
- [ ] Compteur `hit_count` sur redirects **(S)**

---

## Module 5 — Open Source et projets

Tables : `projects`, `project_categories`, `project_technologies`, `project_contributors`

### Important (M)

- [ ] Catalogue projets : nom, description, stack, stage, équipe, GitHub, démo, licence
- [ ] Liste publique : uniquement `review_status = approved`
- [ ] Filtres lecture (technologie, stage, catégorie) — au minimum lecture M, filtres **(S)**

### Important ensuite (S)

- [ ] Soumission projet par membre (`project.submit`) → `pending` **(S)**
- [ ] Validation / rejet éditeur (`project.review`) **(S)**
- [ ] Contributeurs liés aux profils membres **(S)**
- [ ] Page / endpoint « Contribuer » (guide) **(S)**

### Plus tard (C)

- [ ] Sync GitHub (étoiles, dernier commit) **(C)**

---

## Module 6 — Ressources

Tables : `resource_folders`, `resources`, `resource_tags`

### Important (M)

- [ ] Dossiers : un par événement / session (arborescence `parent_id`)
- [ ] Types : slides, video, code, link, document
- [ ] Ressource = fichier (`media_id`) **ou** URL externe
- [ ] Niveaux d’accès : `public` | `members` (`resource.read_members`)
- [ ] Upload / création par éditeurs et Leads (`resource.manage` / `resource.manage_community`)
- [ ] Publication : `status` + `published_at`

### Important ensuite (S)

- [ ] Recherche / filtres (événement, thème, type, année) **(S)**
- [ ] Rattacher un intervenant (`speaker_id`) **(S)**

### Plus tard (C)

- [ ] Compteurs vues / téléchargements **(C)**

---

## Module 7 — Initiatives et programmes

Tables : `programs`, `program_links`, `program_partners`, `key_figures`

### Important (M)

- [ ] Liste programmes (`/programmes`)
- [ ] Fiche : objectif, public, calendrier, conditions, partenaires
- [ ] Liens d’action paramétrables (`program_links` : apply, register, learn_more, website)
- [ ] Chiffres clés modifiables (`key_figures`) — globaux et par programme / édition

### Important ensuite (S)

- [ ] Statut programme : upcoming / open / ongoing / finished **(S)**
- [ ] Chiffres d’impact globaux (accueil) **(S)**
- [ ] Mise en avant `is_featured` sur l’accueil **(S)**

---

## Back-office API (transversal)

Exposé pour le front « Back Stage », pas une UI ici.

- [ ] Routes admin protégées par permission pour chaque type de contenu
- [ ] Modération inscriptions membres + projets soumis **(M)**
- [ ] Gestion redirections + chiffres clés + settings **(M)**
- [ ] Tableau de bord agrégé (membres, events à venir, contenus en attente) **(S)**
- [ ] Export CSV **(S)**

---

## Progression rapide

| Bloc | Statut |
|---|---|
| 0. Socle | ☑ |
| 1. Contenus / accueil | ☑ |
| 2. Membres / annuaire | ☐ |
| 3. Événements | ☐ |
| 4. Festival | ☐ |
| 5. Projets | ☐ |
| 6. Ressources | ☐ |
| 7. Programmes | ☐ |
| Back-office transversal | ☐ |

Quand un module est terminé (tous les **M** cochés), passer la ligne du tableau à ☑.
