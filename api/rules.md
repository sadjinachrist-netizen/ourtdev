# Règles API — ourtdev.com

Document destiné aux développeurs et aux agents IA travaillant sur `api/`.
Stack imposée. Ne pas proposer Nest, Django REST, ni un CMS headless.

## Périmètre

- On travaille **uniquement** dans `api/`.
- `database/` (SADJINA Christ) : schéma source de vérité. Ne pas modifier le SQL sans accord.
- `web/` (KOUTODZO Kodzo Etonam) : hors scope. L’API expose un contrat REST/OpenAPI consommable par Next.js.
- Référence produit : cahier des charges refonte TDEV v1.0 (30/09/2026).

## Stack obligatoire

- **Framework** : FastAPI
- **Architecture** : monolithe modulaire (un seul déploiement, modules par domaine)
- **ORM** : SQLAlchemy 2 async + asyncpg (ou SQLModel si aligné avec l’équipe)
- **Validation** : Pydantic v2
- **Migrations** : Alembic — rester compatible avec `database/01_schema.sql` et `02_seed.sql`
- **Auth** : JWT access + refresh tokens (hashés en base), OAuth GitHub/Google, MFA TOTP pour les admins
- **Tests** : pytest + httpx (AsyncClient)
- **Python** : 3.11+

## Architecture des dossiers

```text
api/
├── app/
│   ├── main.py                 # création de l’app, include_router
│   ├── core/                   # config, db session, security, dependencies
│   ├── shared/                 # erreurs, pagination, i18n helpers, schemas communs
│   └── modules/
│       ├── auth/
│       ├── users/
│       ├── contents/           # pages, articles, partenaires, contact
│       ├── festival/           # éditions, annonces, redirects
│       ├── events/
│       ├── programs/           # programmes + key_figures
│       ├── members/            # profils, annuaire, PII, messages
│       ├── projects/
│       ├── resources/
│       └── media/
├── tests/
├── pyproject.toml
├── .env.example
├── README.md
├── rules.md
└── TODO.md                  # checklist des 7 modules (à cocher)
```

## Checklist des modules

Suivre et cocher la progression dans [`TODO.md`](TODO.md) :
socle → lot 1 (modules 1, 3, 4, 7) → lot 2 (modules 2, 5, 6).

## Règles métier (base de données)

Source : `database/README.md`. À respecter strictement côté API.

1. **Ne jamais** renvoyer `password_hash`, jetons en clair, ni le contenu de `member_pii` sur une route publique.
2. Annuaire : profil visible seulement si `listed_in_directory` est vrai **et** `hidden_at` est vide ; respecter `visibility`, `show_location`, `show_links`.
3. Stocker les jetons (`refresh_tokens`, `one_time_tokens`) et codes MFA de secours **hashés**.
4. Chiffrer `user_mfa.totp_secret_enc` **avant** insertion (jamais en clair).
5. Contenu publiable visible si `status = published` **et** `published_at <= now()` (publication planifiée).
6. i18n : tables `*_translations` ; langue par défaut `fr` ; si traduction manquante, fallback FR.
7. Lead : limité à sa/ses communauté(s) via `user_roles.community_id` (événements / ressources).
8. Permissions : utiliser les codes seedés. Ne pas hardcoder des rôles en contournant `role_permissions`.
9. Toute action back-office significative → `activity_logs` (sans données personnelles).
10. `member_pii` uniquement avec la permission `pii.read`.

## Conventions API

- Préfixe : `/api/v1/...`
- Langue : header `Accept-Language` ou query `?lang=fr|en` (défaut `fr`)
- Erreurs JSON homogènes : `{ "detail": "...", "code": "..." }`
- Pagination : `?page=&page_size=` ; réponse avec `items` + `meta`
- Auth : `Authorization: Bearer <access_token>`
- OpenAPI : tags par module ; pas de champs secrets dans les exemples
- Aucun secret dans le code : `.env` ; fournir `.env.example`

## Git / travail d’équipe

- Branche par fonctionnalité (`feat/auth-login`, `feat/events-list`…) ; pas de commit direct sur `main`
- PR relue par un autre membre
- Ne pas committer `.env`, dumps, secrets
- Ne pas modifier `database/*.sql` ni `web/` dans une PR API sauf demande explicite

## Interdits pour les agents

- Ne pas proposer NestJS, WordPress, Strapi/Directus/Payload comme remplacement de cette API
- Ne pas générer d’exploits, de bypass auth, ni d’accès non autorisé à `member_pii`
- Ne pas fusionner PII dans le profil public
- Ne pas hardcoder des rôles/permissions en contournant `role_permissions`
- Ne pas écrire de code hors de `api/` sauf fichier partagé explicitement demandé