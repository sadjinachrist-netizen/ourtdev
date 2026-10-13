# Ce qu'il faut connaître — API ourtdev

Préfixe de toutes les routes : `/api/v1`.

OpenAPI interactive : http://localhost:8000/docs  
Collection Postman : [`postman/ourtdev-api.postman_collection.json`](postman/ourtdev-api.postman_collection.json)  
Checklist : [`TODO.md`](TODO.md)

Branche en cours du module 3 : `feat/module-3-events`.

## État

| Bloc | Statut |
|---|---|
| Socle (auth, compte, médias, paramètres) | Fait |
| Module 1 — Contenus | Fait |
| Module 2 — Membres / annuaire | Fait |
| Module 3 — Événements | Fait |
| Modules 4 à 7 (festival, projets, ressources, programmes) | Pas faits. Seule la route `GET /…/status` répond `not_implemented`. |

Les tests (`APP_ENV=test pytest`, PostgreSQL allumé) couvrent ces quatre blocs.

## Lancer

```bash
docker compose up -d          # à la racine du repo
cd api
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Santé : `GET /api/v1/health`.

Dans Postman : lancer **Auth / Register** puis **Auth / Login**. Le script enregistre `accessToken`. Les routes admin exigent un compte éditeur ou administrateur.

## Règles communes

- Langue : `?lang=fr` ou `?lang=en`, sinon `Accept-Language`, sinon français.
- Un contenu public (page, article, événement) n'est visible que si `status=published` et `published_at` est passé.
- Mot de passe : minimum 8 caractères. Jamais renvoyer `password_hash`.
- Jeton d'accès : en-tête `Authorization: Bearer …`. Le refresh est opaque ; **Logout** le révoque.
- Inscription : le compte naît `pending`. Avec le réglage `member_validation=email` (valeur par défaut), la vérification de l'email le passe à `active`. Le lien de vérification s'affiche dans la console du serveur en dev.
- MFA : seulement pour un administrateur qui l'a activé. Le login renvoie alors `mfa_required` et `mfa_ticket`, pas les jetons. **MFA verify** termine la connexion (code TOTP ou code de secours).
- OAuth GitHub / Google : `503` tant que les identifiants ne sont pas dans `.env`.
- Formulaires de contact (site et membre) : le champ `website` est un piège anti-robot, il doit rester vide. Limite : 5 envois / 10 minutes / IP.
- Les e-mails, le téléphone et le nom légal ne sortent jamais sur les routes publiques.

## Rôles

Chaque rôle reprend les droits du précédent.

| Rôle | Droits utiles déjà branchés |
|---|---|
| Membre | Modifier son profil, s'inscrire à un événement |
| Lead | Proposer un événement, uniquement pour sa `community_id` |
| Éditeur | Pages, équipe, partenaires, articles, contact, chiffres clés, médias, événements (y compris publier), valider un membre, masquer un profil, attribuer un badge, créer une compétence |
| Administrateur | Tout l'éditeur, plus paramètres du site, export CSV des membres, lecture des données personnelles |

L'éditeur n'a pas `member.export` ni `pii.read`.

## Socle

| Méthode | Route | Qui |
|---|---|---|
| GET | `/health` | Public |
| POST | `/auth/register` | Public |
| POST | `/auth/verify-email` | Public, corps `{ "token" }` |
| POST | `/auth/login` | Public |
| POST | `/auth/refresh` | Public, corps `{ "refresh_token" }` |
| POST | `/auth/logout` | Public, même corps |
| POST | `/auth/forgot-password` | Public |
| POST | `/auth/reset-password` | Public, `{ "token", "new_password" }` |
| GET | `/auth/oauth/{github\|google}/authorize` | Public |
| GET | `/auth/oauth/{provider}/callback?code=` | Callback du fournisseur |
| POST | `/auth/mfa/setup` | Connecté |
| POST | `/auth/mfa/enable` | Connecté, `{ "code" }` à 6 chiffres |
| POST | `/auth/mfa/verify` | `{ "mfa_ticket", "code" }` |
| GET | `/users/me` | Connecté. Enregistre aussi `userId` dans Postman |
| GET | `/settings` | Public |
| GET | `/settings/all` | `settings.manage` |
| PATCH | `/settings/{clé}` | `settings.manage`, corps `{ "value" }` |
| POST | `/media` | `media.manage`, formulaire `file`, `alt_text`, `language_code` |
| GET | `/media/{id}` | Public |

Types de fichier acceptés : image, PDF, texte, vidéo.

## Module 1 — Contenus

Public :

| Méthode | Route |
|---|---|
| GET | `/home` |
| GET | `/pages/{slug}` |
| GET | `/team` |
| GET | `/partners` |
| GET | `/articles` et `/articles/{slug}` |
| POST | `/contact` |

Admin (éditeur) :

| Méthode | Route | Permission |
|---|---|---|
| GET, POST, PATCH | `/admin/pages`, `/admin/pages/{id}` | `page.manage` |
| POST | `/admin/pages/{id}/publish` | `page.manage` |
| POST, PATCH | `/admin/team`, `/admin/team/{id}` | `page.manage` |
| POST, PATCH | `/admin/partners`, `/admin/partners/{id}` | `partner.manage` |
| POST, PATCH | `/admin/articles`, `/admin/articles/{id}` | `article.manage` |
| GET, PATCH | `/admin/contact`, `/admin/contact/{id}` | `contact.read` |
| GET, PATCH | `/admin/key-figures`, `/admin/key-figures/{id}` | `key_figure.manage` |

Statuts d'un message de contact : `new`, `read`, `handled`, `spam`.

Une page ou un article a une traduction `fr` et, si on la fournit, `en`. Les deux se lisent avec `?lang=`.

## Module 2 — Membres

| Méthode | Route | Qui |
|---|---|---|
| GET | `/directory` | Public. Filtres : `q`, `technology`, `city`, `country_code`, `member_status`, `page` |
| GET | `/directory/{handle}` | Public |
| POST | `/directory/{handle}/contact` | Public, si le profil a `allow_contact` |
| GET, PUT | `/members/me` | Connecté, permission `profile.edit_own` |
| GET, PUT | `/members/me/pii` | Le membre lui-même |
| GET | `/members/me/dashboard` | Connecté. Événements, projets et ressources liés au compte |
| GET | `/technologies` | Public |
| POST | `/admin/technologies` | `member.moderate`. Le `name` est unique |
| POST | `/admin/members/{userId}/approve` | `member.approve` |
| POST | `/admin/members/{userId}/visibility` | `member.moderate`, corps `{ "hidden": true }` |
| POST | `/admin/members/{userId}/badges` | `member.moderate`. Codes : `lead`, `contributor`, `speaker`, `festival_alumni` |
| GET | `/admin/members/{userId}/pii` | `pii.read` |
| GET | `/admin/members/export` | `member.export`. CSV. Prénom, nom et téléphone seulement avec `pii.read` |

Annuaire : le profil doit être listé, avec consentement, et non masqué.

Visibilité :

- `public` : tout le monde
- `members` : seulement un visiteur connecté
- `private` : personne, sauf le propriétaire

`show_location` et `show_links` masquent la ville et les liens (GitHub, LinkedIn, portfolio) pour les autres. Le propriétaire les voit toujours.

Handle : 3 à 30 caractères, `a-z`, `0-9`, `_` et `-`.

## Module 3 — Événements

Public :

| Méthode | Route | Détail |
|---|---|---|
| GET | `/events` | `when=upcoming` (défaut), `past` ou `all`. Filtres `type`, `year`, `city`, `format` (`onsite`, `online`, `hybrid`) |
| GET | `/events/timeline` | Événements publiés avec `show_in_timeline` |
| GET | `/events/{slug}` | Fiche |
| GET | `/events/{slug}/calendar.ics` | Fichier calendrier |
| POST | `/events/{slug}/register` | Compte connecté. Rôle : `attendee`, `volunteer`, `organizer`. Une seule inscription. Refusée si l'événement est terminé |

La fiche renvoie le titre, les dates, le lieu, la description, les intervenants, les partenaires, la galerie, `replay_url`, `registration_url`, et le dossier de ressources lié.

Admin :

| Méthode | Route | Qui |
|---|---|---|
| POST | `/admin/events` | Éditeur (`event.manage`) ou lead (`event.propose`) |
| PATCH | `/admin/events/{id}` | Le même. Un lead ne touche que les événements de sa communauté |
| POST | `/admin/events/{id}/publish` | Éditeur seulement |
| POST | `/admin/speakers` | Éditeur ou lead |
| POST | `/admin/events/{id}/speakers` | Corps `{ "speaker_id", "role", "position" }`. Rôles : `speaker`, `panelist`, `moderator`, `trainer` |
| POST | `/admin/events/{id}/media` | `{ "kind": "photo"\|"video", "media_id" ou "url" }` |
| POST | `/admin/events/{id}/partners` | `{ "partner_id" }` — le partenaire se crée dans le module 1 |

Un lead envoie `community_id` égal à la sienne. Il ne peut pas publier. S'il n'a qu'une communauté, `community_id` peut être omis.

À la publication, l'API crée un dossier dans `resource_folders`, avec le même slug que l'événement et les titres comme noms de dossier. La fiche expose `resource_folder.id` et `resource_folder.slug`.

Types d'événement : `meetup`, `workshop`, `conference`, `hackathon`, `training`, `festival`, `other`.

Deux limites :

- `participants_count` et `sessions_count` sont saisis à la main. Ils n'apparaissent sur la fiche que si `show_stats` est vrai. Ils ne sont pas calculés depuis les inscriptions.
- Le dossier de ressources est créé, mais les fichiers et liens à l'intérieur (module 6) ne sont pas encore codés.

## Pas encore fait

Festival, projets open source, ressources (hors le dossier créé par un événement) et programmes. Leurs routes `/status` répondent, le reste non.
