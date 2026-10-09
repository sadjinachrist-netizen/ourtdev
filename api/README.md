# API back-end — ourtdev.com

API FastAPI (monolithe modulaire) : contenus, annuaire, événements, festival, projets, ressources, programmes, authentification et back-office.

Responsable : KPARA Gedeon. Authentification et rôles : SADJINA Christ.

- Règles agents / conventions : [`rules.md`](rules.md)
- Checklist modules : [`TODO.md`](TODO.md)
- Schéma PostgreSQL : [`../database/README.md`](../database/README.md)

## Prérequis

- Python 3.11+
- Docker (PostgreSQL via Compose à la racine du repo)

## Base de données

Depuis la racine du monorepo :

```bash
docker compose up -d
```

Applique automatiquement `database/01_schema.sql` et `02_seed.sql`.

## Installation

```bash
cd api
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e ".[dev]"     # pytest, ruff
cp .env.example .env
```

## Lancer

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Health : http://localhost:8000/api/v1/health
- OpenAPI : http://localhost:8000/docs
- Fichiers médias : http://localhost:8000/media/...

## Tests

```bash
# Postgres doit tourner (docker compose up -d)
APP_ENV=test pytest
```

## Architecture

```text
app/
├── main.py
├── core/          # config, db, security, dependencies
├── shared/        # erreurs, pagination, i18n
└── modules/       # auth, users, contents, festival, events,
                   # programs, members, projects, resources, media
```

Préfixe API : `/api/v1/...`. Le schéma SQL source de vérité reste dans `database/` ; Alembic sera ajouté quand les modèles SQLAlchemy seront mappés.
