# CEF Desk

Logiciel de gestion du Cercle d'Escrime de Founex (CEF), développé sur mesure pour remplacer ClubDesk et corriger ses limitations (personnalisation des fiches membres, facturation/QR-factures, formulaires d'inscription en ligne, exports de données).

**Toujours lire ce fichier en entier au début de chaque session, avant toute tâche.**

## Où trouver le cahier des charges complet

Le document de référence fonctionnel ET technique complet — tous les modules détaillés, toutes les décisions prises avec Alex, tous les points encore ouverts — est dans [`docs/cahier-des-charges.md`](docs/cahier-des-charges.md) à la racine de ce dépôt.

**Règle impérative : consulter ce document avant de commencer à travailler sur un module qui n'est pas encore implémenté.** Il contient le détail exact des champs, des règles métier (barèmes, statuts, logique de validation), et des exigences de sécurité — ne pas improviser une conception différente de ce qui y est écrit sans en parler explicitement à Alex d'abord.

Si une décision de conception change en cours de développement, mettre à jour `docs/cahier-des-charges.md` en conséquence (pas seulement ce fichier), pour que le document de référence reste exact.

## État d'avancement

*(Section à tenir à jour à la fin de chaque session de travail significative — remplacer par l'état réel, ne pas laisser ce paragraphe tel quel une fois du code écrit.)*

- Statut : planification fonctionnelle et technique terminée (cahier des charges finalisé avec Alex). Aucune ligne de code métier écrite pour l'instant.
- Développement prévu **entièrement en local** pour l'instant — pas d'hébergement souscrit, pas de coordonnées bancaires réelles du club disponibles (utiliser des valeurs placeholder clairement identifiées comme telles). Cf. cahier des charges section 11.

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
