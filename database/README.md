# Base de données ourtdev.com

Schéma PostgreSQL de la plateforme communautaire TDEV, conforme au cahier des charges de refonte (v1.0 du 30/09/2026).

Version : 0.2. Responsable : SADJINA Christ.

## Fichiers

| Fichier | Contenu |
|---|---|
| `01_schema.sql` | Création des tables, types, index, contraintes et triggers |
| `02_seed.sql` | Données de référence : langues, rôles, permissions, badges, niveaux de partenariat, pages de base, chiffres clés, paramètres |

Compatible PostgreSQL 13 et plus, testé sur PostgreSQL 18. Seule extension requise : `citext`.

## Installation en local

### Avec pgAdmin

1. Clic droit sur *Databases*, puis *Create*, puis *Database*. Nom : `ourtdev`.
2. Clic droit sur `ourtdev`, puis *Query Tool*.
3. Ouvrir `01_schema.sql` et l'exécuter. Résultat attendu : `COMMIT`.
4. Ouvrir `02_seed.sql` et l'exécuter. Résultat attendu : `COMMIT`.

### En ligne de commande

```bash
createdb -U postgres ourtdev
psql -U postgres -d ourtdev -v ON_ERROR_STOP=1 -f 01_schema.sql
psql -U postgres -d ourtdev -v ON_ERROR_STOP=1 -f 02_seed.sql
```

`02_seed.sql` ne s'exécute qu'une fois : relancé, il échoue sur les doublons.

### Vérification

```sql
SELECT r.label, count(*) AS permissions
FROM roles r JOIN role_permissions rp ON rp.role_id = r.id
GROUP BY r.id, r.label ORDER BY r.id;
```

Résultat attendu : Membre 3, Lead de communauté 5, Éditeur 18, Administrateur 24.

## Organisation

La base compte 70 tables : 51 tables principales et 19 tables de traduction.

| Bloc | Module du cahier | Tables principales |
|---|---|---|
| 1. Socle | Back-office, sécurité | `languages`, `users`, `oauth_accounts`, `refresh_tokens`, `one_time_tokens`, `user_mfa`, `mfa_recovery_codes`, `communities`, `roles`, `permissions`, `role_permissions`, `user_roles`, `media_files`, `activity_logs`, `site_settings`, `redirects` |
| 2. Contenus | Module 1 | `pages`, `team_members`, `partners`, `partner_levels`, `articles`, `article_categories`, `tags`, `article_tags`, `contact_messages` |
| 3. Festival | Module 4 | `festival_editions`, `announcements` |
| 4. Événements | Module 3 | `events`, `event_media`, `speakers`, `event_speakers`, `event_partners`, `event_participants` |
| 5. Programmes | Module 7 | `programs`, `program_links`, `program_partners`, `key_figures` |
| 6. Membres | Module 2 | `member_profiles`, `member_pii`, `technologies`, `member_technologies`, `badges`, `member_badges`, `member_messages` |
| 7. Projets | Module 5 | `projects`, `project_categories`, `project_technologies`, `project_contributors` |
| 8. Ressources | Module 6 | `resource_folders`, `resources`, `resource_tags` |

## Principes de conception

**Bilingue.** Chaque contenu traduisible a une table `<contenu>_translations`, avec une ligne par langue. Ajouter une langue revient à ajouter une ligne dans `languages`, sans modifier le schéma. Si une traduction manque, l'API affiche la langue par défaut (français).

**Publication.** Les contenus publiables (pages, articles, événements, programmes, éditions, ressources) ont un statut `draft`, `in_review`, `published` ou `archived`, et une date `published_at`. Un contenu est visible si son statut est `published` et que `published_at` est passé, ce qui permet la publication planifiée.

**Rôles.** Quatre rôles stockés : Membre, Lead de communauté, Éditeur, Administrateur (le visiteur n'est pas connecté). Le rôle Lead est rattaché à une ou plusieurs communautés dans `user_roles.community_id` : un Lead n'agit que sur les événements et ressources de sa communauté. Les badges (Lead, contributeur, speaker, alumni) sont affichés sur le profil et ne donnent aucun droit.

**Données personnelles.** Le profil public (`member_profiles`) n'utilise qu'un pseudonyme et les informations que le membre choisit de montrer. Nom, prénom et téléphone sont isolés dans `member_pii`, lisible uniquement avec la permission `pii.read`. Un membre ne peut apparaître dans l'annuaire qu'après avoir donné son consentement, dont la date est enregistrée.

**Médias.** Images et fichiers sont centralisés dans `media_files`, avec un texte alternatif par langue pour l'accessibilité.

**Traçabilité.** Toute action du back-office est enregistrée dans `activity_logs`, sans données personnelles.

**Festival.** Le lien permanent `/festival/<année>` pointe vers `festival_editions.target_url`, modifiable depuis le back-office. Les anciennes URL sont gérées dans `redirects` (301).

## Règles à appliquer côté API

- Ne jamais renvoyer `password_hash`, les jetons, ni le contenu de `member_pii` sur une route publique.
- Afficher un profil dans l'annuaire seulement si `listed_in_directory` est vrai et `hidden_at` est vide, en respectant `visibility`, `show_location` et `show_links`.
- Les jetons (`refresh_tokens`, `one_time_tokens`) et les codes de secours sont stockés sous forme de hash.
- Le secret de double authentification (`user_mfa.totp_secret_enc`) est chiffré par l'API avant stockage.
- `updated_at` est mis à jour automatiquement par trigger.

## Points à confirmer avec le bureau TDEV

- Liste des communautés (antennes et groupes) et droits exacts des Leads.
- Mode de validation des inscriptions : email, administrateur ou les deux (paramètre `member_validation`).
- Grille des niveaux de partenariat.
- Valeurs des chiffres clés (2 000 membres actifs, nombre de rencontres à mettre à jour).
