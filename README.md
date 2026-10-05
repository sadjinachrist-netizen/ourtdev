# ourtdev.com

Refonte de la plateforme communautaire TDEV (Chantier 4 du TDEV Festival 2026) : site institutionnel, annuaire des membres, événements et meetups, éditions du Festival, projets open source, ressources partagées et programmes de la communauté, avec un back-office d'administration.

Référence : cahier des charges de refonte, version 1.0 du 30/09/2026.

| Dossier | Contenu | Responsable |
|---|---|---|
| `database/` | Schéma PostgreSQL et données de référence | SADJINA Christ |
| `api/` | API back-end | KPARA Gedeon |
| `web/` | Front-end Next.js | KOUTODZO Kodzo Etonam |

Protection des données personnelles des membres : Peace.

## Règles de travail

- Une branche par fonctionnalité (`feat/annuaire`, `fix/connexion`...), pas de commit direct sur `main`.
- Chaque Pull Request est relue par un autre membre avant d'être fusionnée.
- Aucun secret dans le code : mots de passe et clés vont dans un fichier `.env`, qui n'est pas versionné.

Installation de la base en local : voir [`database/README.md`](database/README.md).
