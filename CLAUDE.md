# CEF Desk

Logiciel de gestion du Cercle d'Escrime de Founex (CEF), développé sur mesure pour remplacer ClubDesk et corriger ses limitations (personnalisation des fiches membres, facturation/QR-factures, formulaires d'inscription en ligne, exports de données).

**Toujours lire ce fichier en entier au début de chaque session, avant toute tâche.**

## Où trouver le cahier des charges complet

Le document de référence fonctionnel ET technique complet — tous les modules détaillés, toutes les décisions prises avec Alex, tous les points encore ouverts — est dans [`docs/cahier-des-charges.md`](docs/cahier-des-charges.md) à la racine de ce dépôt.

**Règle impérative : consulter ce document avant de commencer à travailler sur un module qui n'est pas encore implémenté.** Il contient le détail exact des champs, des règles métier (barèmes, statuts, logique de validation), et des exigences de sécurité — ne pas improviser une conception différente de ce qui y est écrit sans en parler explicitement à Alex d'abord.

Si une décision de conception change en cours de développement, mettre à jour `docs/cahier-des-charges.md` en conséquence (pas seulement ce fichier), pour que le document de référence reste exact.

## État d'avancement

*(Section à tenir à jour à la fin de chaque session de travail significative.)*

**Dernière mise à jour : 19 septembre 2026** (code poussé sur GitHub `Alexode05/CEF_Desk`, branche `main`). Les 8 modules de la V1 sont implémentés et fonctionnent en local (SQLite). Développement toujours **entièrement en local** — pas d'hébergement, coordonnées bancaires = placeholders marqués `[PLACEHOLDER]` dans « Paramètres du club ».

Installation/lancement : voir `README.md` (`pip install -r requirements.txt`, `.env`, `migrate`, `seed_reference_data`, `runserver`). Tests : `python manage.py test apps` (21 tests, verts).

| Module | État | Où |
|---|---|---|
| Fondations, connexion, création de compte (code d'invitation), **A2F TOTP obligatoire** | Terminé | `apps/accounts` (middleware `LoginAndTwoFactorRequiredMiddleware`) |
| Tableau de bord (compteurs, factures en attente + prochain rappel, inscriptions à valider, notes, to-do tracée) + **Paramètres du club** (point de configuration unique) | Terminé | `apps/dashboard` |
| Contacts/Membres : 3 profils, ID `prenom.nom` + homonymes, catégorie d'âge auto, groupes, catégories fixes, recherche, filtres sur tout champ, colonnes personnalisables par utilisateur, vues enregistrées, champs personnalisés depuis l'UI, import CSV, modification de masse, validation d'inscription | Terminé | `apps/members` (`fields.py` = registre des champs partagé avec formulaires/exports) |
| Comptabilité : barème 3×4, facture PDF (en-tête club + bloc QR-bill `qrbill`), référence QR/SCOR via `python-stdnum`, archivage auto dans Fichiers, envoi email Cc trésorier, lots en 2 étapes, relances à 1 mois (`send_reminders`), pointage manuel « payée » | Terminé (voir point ouvert SIX ci-dessous) | `apps/billing` |
| Fichiers : dossiers Club/Direction/Public, upload/téléchargement/renommage/suppression | Terminé | `apps/documents` |
| Formulaires : éditeur structuré adossé aux champs de la fiche, champ « Type d'inscription » Mineur/Majeur, règles conditionnelles, page publique + honeypot + délai minimal, fiche « en attente », email récapitulatif complet au secrétariat, copie JSON du modèle dans Club/Formulaires | Terminé | `apps/formbuilder` |
| Mailing : listes dynamiques/statiques, email groupé individuel, exclusion ponctuelle, passerelle vers la facturation groupée | Terminé | `apps/mailing` |
| Export CSV 3 variantes (Excel Windows / macOS / Numbers), AVS exclu sauf choix explicite | Terminé (ouverture réelle dans Excel/Numbers **non testée** — à faire par Alex) | `apps/exports` |
| Sauvegardes : commande `backup` (BD + media, rétention 30 j) à planifier | Terminé (planification à faire chez l'hébergeur) | `apps/dashboard/management/commands/backup.py` |

**Points à traiter avec Alex (ne pas trancher seul) :**
- **Validation SIX** : le portail officiel https://validation.iso-payments.ch exige un compte utilisateur → Alex doit s'y inscrire et déposer `docs/exemples/exemple-qr-facture.pdf`. En attendant, `python manage.py check_qrbill` décode le QR du PDF réel et le vérifie contre la norme (passe : adresses structurées obligatoires IG 2.3, référence QR valide, 46 mm, position OK).
- Montants des 12 tarifs (barème vide → facturation bloquée pour les membres concernés).
- Règle exacte de calcul des catégories d'âge : implémentée = âge atteint dans l'année civile de fin de saison (saison démarre en septembre, réglable) ; U8 <8, U10 <10, U12 <12, U14 <14, U17 <17, U20 <20, Sénior 20-39, Vétéran ≥40. À confirmer avec le règlement Swiss Fencing.
- Création de compte comité : protégée par un **code d'invitation** (`CEF_REGISTRATION_CODE` dans `.env`) — décision prise pour éviter une inscription ouverte à tous ; à valider.
- Un seul niveau de relance (répété tous les 30 jours tant que la facture est impayée) ; le trésorier est en Cc des relances comme des factures.
- Texte des emails de facture/relance : modifiable dans Paramètres du club (variables `{prenom}`, `{nom}`, `{saison}`, `{montant}`, `{echeance}`, `{numero}`).
- Ouverture réelle des 3 variantes CSV dans Excel Windows, Numbers et un tableur mobile à tester par Alex.

**Bugs connus / limites :** aucun bug bloquant connu. HTTPS local non activé (réglages HTTPS prêts via `DJANGO_FORCE_HTTPS=True` pour la production). Réinitialisation de l'A2F d'un utilisateur : via l'administration technique `/admin/` (supprimer son appareil TOTP).

## Stack retenue (cahier des charges section 11)

- Backend : **Python / Django**
- Base de données : **PostgreSQL** (une base SQLite locale est acceptable pour le développement si plus simple à mettre en place, tant que le code reste compatible PostgreSQL pour la mise en production)
- Génération des QR-factures suisses : bibliothèque `qrbill` (ou équivalent conforme à la norme officielle SIX) — ne jamais redessiner le gabarit à la main
- Hébergement cible (plus tard seulement, pas maintenant) : hébergeur basé en Suisse (ex. Infomaniak)

## Exigences de sécurité non négociables (cahier des charges section 11)

Ce projet traite des données personnelles sensibles, y compris de mineurs, et des numéros AVS. Ces points doivent être respectés dès les premières briques de code, pas ajoutés après coup :

- Authentification obligatoire sur toute page de gestion (aucun accès anonyme, en dehors des formulaires publics d'inscription)
- **A2F (authentification à deux facteurs) obligatoire** pour tous les comptes du comité — configurée à la création du compte, demandée à chaque connexion
- HTTPS partout
- Secrets (mot de passe base de données, identifiants email, futures coordonnées bancaires, clé secrète Django) en variables d'environnement — jamais en clair dans le code, jamais committés dans le dépôt
- Numéro AVS traité comme donnée sensible : non affiché par défaut dans les listes, exclu par défaut des exports (sauf sélection explicite de la colonne)
- Sauvegardes automatiques régulières prévues pour la base de données et les fichiers archivés (factures, soumissions de formulaires)
- Protection anti-spam de type honeypot sur les formulaires publics (pas de captcha intrusif)
- Utiliser les protections par défaut de Django (CSRF, échappement automatique, ORM contre l'injection SQL) — ne jamais les contourner pour "simplifier"

## Décisions de conception clés (résumé — détail complet et exhaustif dans le cahier des charges)

- **3 profils de fiche membre distincts** avec des champs différents : Mineur, Majeur, Essai (section 4). Ne pas fusionner ces profils en un seul formulaire générique sans distinction.
- Passage **Essai → Mineur/Majeur** (essai concluant) : la fiche "Essai" est supprimée, une nouvelle fiche est recréée de zéro à partir du formulaire d'inscription définitif (pas de migration/fusion de données).
- Passage **Mineur → Majeur** (majorité) : aucun changement de la fiche existante — elle garde son jeu de champs "Mineur".
- ID membre généré automatiquement (`prenom.nom`), avec gestion des doublons homonymes à prévoir.
- Catégorie d'âge (U8/U10/U12/U14/U17/U20/Sénior/Vétéran) calculée automatiquement depuis la date de naissance.
- Soumission de formulaire → fiche créée avec statut "en attente de validation", jamais directement "Actif" ; validation manuelle par le comité.
- Formulaires : **éditeur structuré** (liste de champs configurables avec règles conditionnelles simples), pas un éditeur visuel type Google Forms pour la V1 — les champs du formulaire doivent correspondre exactement aux champs des fiches membres.
- Facturation : barème = 3 modalités d'entraînement × 4 tranches tarifaires (montants à obtenir d'Alex) ; réduction famille de -100 CHF dès le 2ᵉ enfant ; tranche tarifaire/statut étudiant/réduction famille saisis manuellement par le comité à la validation (pas demandés dans le formulaire public).
- Génération et envoi des factures **en deux étapes distinctes** (génération groupée avec relecture possible, puis envoi groupé séparé).
- Trésorier en **copie systématique (Cc)** sur les emails de facturation, adresse configurée une seule fois dans les paramètres du club.
- Relance automatique si facture impayée **1 mois** après édition ; validation du paiement **manuelle** (case à cocher dans la liste des factures en attente).
- Chaque facture PDF générée est **archivée automatiquement** dans l'espace de stockage de fichiers.
- Comptabilité limitée **aux cotisations uniquement** pour la V1.
- Export CSV avec **3 variantes** (Windows/iOS/Android, macOS, Numbers) — attention à bien gérer séparateur/encodage/fin de ligne pour chacune, tester l'ouverture réelle dans chaque appli.
- Export Jeunesse+Sport **abandonné**, pas dans le périmètre.
- Automatisations IA **hors périmètre pour la V1**.

## Conventions de travail avec Claude Code

- Relire ce fichier et `docs/cahier-des-charges.md` en entier en début de session.
- Mettre à jour la section "État d'avancement" ci-dessus à la fin de chaque session de travail significative (modules terminés, en cours, bugs connus).
- Ne jamais prendre une décision de conception qui contredit le cahier des charges sans le signaler explicitement à Alex — poser la question plutôt que de trancher seul sur un point métier (barèmes, règles de validation, etc.).
- Le développement se fait en local jusqu'à nouvel ordre (pas d'hébergement souscrit) — cf. section 11 du cahier des charges pour le séquencement prévu.
- **Committer et pousser régulièrement** : un commit par étape cohérente (module, correctif, mise à jour de doc), avec un message en français décrivant le *pourquoi*, puis `git push origin main` dès que l'étape est vérifiée (tests verts, page testée). Ne jamais terminer une session avec du travail non committé ou non poussé — le dépôt GitHub (`Alexode05/CEF_Desk`) est la sauvegarde de référence du code. Ne jamais committer `.env`, `db.sqlite3`, `media/`, `backups/` (déjà dans `.gitignore`).
