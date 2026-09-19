# Cahier des charges — Logiciel de gestion du CEF (remplacement de ClubDesk)

*Document vivant : à compléter au fil des échanges avant de passer au code. Chaque section garde les points encore ouverts en évidence.*

## Table des matières

1. [Contexte et objectif](#1-contexte-et-objectif)
2. [Utilisateurs](#2-utilisateurs)
3. [Structure générale de l'application](#3-structure-générale-de-lapplication)
4. [Module Contacts / Membres](#4-module-contacts--membres)
5. [Module Comptabilité / Facturation](#5-module-comptabilité--facturation)
6. [Espace Stockage de fichiers](#6-espace-stockage-de-fichiers)
7. [Module Formulaires (inscription et autres)](#7-module-formulaires-inscription-et-autres)
8. [Module Mailing groupé](#8-module-mailing-groupé)
9. [Module Inscriptions](#9-module-inscriptions)
10. [Export de données](#10-export-de-données)
11. [Choix techniques](#11-choix-techniques)

## 1. Contexte et objectif

Le Cercle d'Escrime de Founex (CEF) utilise actuellement ClubDesk pour la gestion du club, mais l'outil est jugé peu pratique sur plusieurs aspects clés : personnalisation des fiches membres, gestion des factures (génération et envoi groupés), formulaires d'inscription en ligne, et export des données.

L'objectif est de concevoir un logiciel sur mesure, avec une structure générale proche de ClubDesk (pour ne pas dérouter le comité), mais qui corrige ces points de friction et reste facilement modifiable/extensible dans le temps (y compris, plus tard, avec des automatisations basées sur l'IA).

Ce document sert de cahier des charges de référence. Il sera ensuite traduit en un prompt structuré à donner à un outil de génération de code (Fable 5) pour la réalisation.

## 2. Utilisateurs

- **Phase 1 (actuelle) :** usage exclusivement réservé au comité du CEF.
- **Phase future (à envisager, pas prioritaire) :** ouverture possible aux parents/membres pour l'auto-inscription ou la consultation de leurs informations.

## 3. Structure générale de l'application

Reprend les grandes sections de ClubDesk, avec un périmètre ajusté :

| Section | Priorité | Statut |
|---|---|---|
| Tableau de bord (notes + widgets visibles par tout le comité) | Souhaité | À définir plus précisément |
| Contacts / Membres | **Priorité 1** | Détaillé ci-dessous |
| Comptabilité / Facturation | **Priorité 1** | Détaillé ci-dessous |
| Formulaires d'inscription en ligne | **Priorité 1** (lié aux Contacts) | Détaillé ci-dessous |
| Envoi de mails groupés | **Priorité 1** | Détaillé section 8 |
| Calendrier | Non indispensable pour l'instant | Reporté |
| Espace site web du club | Optionnel, à clarifier | En attente d'info sur l'usage actuel dans ClubDesk |

### Interface générale

**Connexion :**
- Une **page de connexion** est nécessaire pour accéder à l'interface de gestion (rien d'accessible sans être connecté, en dehors des formulaires publics, section 7).
- Cette page permet aussi bien la **création de nouveaux comptes** (pour ajouter un membre du comité) que la **connexion** avec un compte existant.
- **Authentification à deux facteurs (A2F) mise en place** dès la V1 (et non simplement "recommandée" — cf. section 11 "Exigences de sécurité", mis à jour en conséquence) : à l'inscription/première connexion, le compte doit configurer l'A2F (ex. application d'authentification type Google Authenticator/Authy — TOTP), puis la saisir à chaque connexion en plus du mot de passe.
- **Décision d'implémentation (19.09.2026, à confirmer par Alex) :** la création de compte depuis la page de connexion est protégée par un **code d'invitation** du comité (variable d'environnement `CEF_REGISTRATION_CODE`), pour qu'une personne extérieure ne puisse pas créer un compte. Code vide = création de compte désactivée.

**Style visuel :**
- Rendu **professionnel** (sobre, soigné — cohérent avec le fait que certains documents générés, comme les factures, sont envoyés directement aux membres, section 5).
- Mais **convivial et facile à prendre en main** pour le comité : pas d'interface austère ou complexe à l'usage malgré le rendu professionnel — priorité à la clarté (hiérarchie visuelle nette, actions principales facilement identifiables, cohérence des couleurs/composants d'un écran à l'autre), dans l'esprit de ce qu'on a décrit pour l'espace Contacts (section 4) : structure lisible, pas surchargée.

### Paramètres du club

**Décision (19.09.2026, demande d'Alex) :** l'écran « Paramètres du club » est le point de configuration central. Il contient :
- l'identité du club et le compte bancaire des QR-factures (placeholders tant que les vraies coordonnées ne sont pas fournies) ;
- **les adresses email du comité** : trésorier-ère (Cc systématique des factures et relances), secrétariat (notifications d'inscription), président-e, vice-président-e, vérificateur des comptes ;
- la saison, les délais de paiement et de relance, les textes des emails de facture et de relance (valables pour les cotisations comme pour les factures manuelles, variables `{titre}`, `{objet}`, `{destinataire}`, `{numero}`, `{montant}`, `{echeance}`, `{saison}`, `{prenom}`, `{nom}`, `{modalite}`) ;
- un accès à l'**éditeur « Modèle des fiches membres »** (section 4).

### Détail — Tableau de bord

**Widgets (V1) :**
- **Nombre de membres actifs** (compteur simple, basé sur le statut "Actif" en section 4).
- **Factures en attente de paiement**, avec la **date du prochain rappel** affichée pour chacune (lié au mécanisme de relance à 1 mois, section 5).
- **Dernières inscriptions en attente de validation** (lié au statut "en attente de validation", section 4) — permet au comité de voir d'un coup d'œil ce qui reste à traiter.
- **Notes façon post-it** : bloc de texte libre, modifiable par tout le comité, visible par tout le comité (pense-bête partagé, pas lié à un dossier/personne en particulier).
- **To-do liste** partagée, modifiable par tout le comité (ajouter/cocher/supprimer des tâches).

**Droits d'accès :** tout le comité peut modifier le tableau de bord (notes et to-do liste comprises) — pas de restriction par rôle pour la V1, cohérent avec le fait que l'usage est réservé au comité (section 2).

**Décisions :**
- Les widgets "factures en attente" et "dernières inscriptions en attente" sont **cliquables** : un clic sur une ligne amène directement à la facture ou à la fiche concernée.
- **Notes (post-it)** : pas de traçabilité nécessaire, simple bloc modifiable.
- **To-do liste** : **avec traçabilité** — qui a créé/coché/modifié quelle tâche et quand.

## 4. Module Contacts / Membres

### Problèmes actuels avec ClubDesk
- Impossible de personnaliser la fiche membre (noms de champs figés, pas d'ajout de champs propres au club).
- Pas de formulaire d'inscription en ligne qui corresponde vraiment à la fiche membre voulue.
- Recopie manuelle et chronophage des données du formulaire d'inscription vers la fiche contact.
- Filtrage limité des listes de membres selon des critères propres au club.

### Fonctionnalités souhaitées
- **Fiches membres personnalisables** : possibilité d'ajouter/modifier des champs facilement depuis l'interface (pas besoin de toucher au code à chaque fois). À terme, au moins l'ajout de champs simples doit être possible depuis l'UI, sans repasser par Fable 5/le code — cf. section 7 (éditeur structuré de champs, partagé avec les formulaires).
- **Plusieurs types de fiches selon le profil** :
  - Majeur autonome (inscrit lui-même, responsable de ses infos).
  - Mineur avec responsable(s) légal(aux) (champs contact parent obligatoires).
  - Cours d'essai (fiche allégée, moins d'informations demandées).
- **Formulaire d'inscription en ligne** généré à partir de la structure de la fiche membre (les champs du formulaire correspondent 1:1 aux champs de la fiche), pour éviter tout écart entre les deux — cf. section 7.
- **Création automatique de la fiche contact** dès la soumission du formulaire en ligne — zéro recopie manuelle.
- **Filtres et vues personnalisées** sur la liste des membres, basés sur n'importe quel champ (y compris des champs custom) — ex. : voir en un coup d'œil qui a payé sa facture, à qui elle a été envoyée, qui est en cours d'essai, etc.

### Champs de la fiche membre (V1) — référence : capture d'écran ClubDesk fournie

L'agencement général de la fiche (onglets "Générales" / "Finance", disposition en deux colonnes) est repris tel quel. Trois variantes de fiche selon le profil (cf. section "Fonctionnalités souhaitées" ci-dessus) :

**Profil Mineur**

| Champ | Détail |
|---|---|
| Titre | Liste déroulante : Monsieur, Madame, Famille, Aux parents de |
| Prénom, Nom | Texte |
| Adresse | Texte |
| Code postal, Ville, Pays | Pays = liste déroulante |
| Sexe | Liste déroulante |
| Entrée, Sortie, Statut | Dates + statut en liste déroulante : Actif, Licence uniquement, Essai |
| ID, Rôle | ID = généré automatiquement (`prenom.nom`) ; Rôles = **plusieurs rôles possibles** : on choisit dans une liste (Tireur-euse, Coach, Maître d'arme, Membre, Comité, Président-e, Vice-président-e, Trésorier-ère, Secrétaire, Vérificateur des comptes) et chaque rôle retenu s'affiche en dessous sous forme de badge que l'on peut retirer (×) |
| N° AVS | Texte (format numéro AVS suisse) |
| Latéralité | Liste déroulante (ex. Droite/Gauche) |
| N° de licence | Texte |
| Téléphone escrimeur.euse | Texte |
| Téléphone parent 1 | Texte |
| Téléphone parent 2 | Texte |
| Email élève | Email |
| Email parent 1 | Email |
| Email parent 2 | Email |
| Date de naissance | Date |
| Catégorie | **Calculée automatiquement** à partir de la date de naissance : U8, U10, U12, U14, U17, U20, Sénior, Vétéran |
| Nationalité | Liste déroulante |
| Groupe | Groupe secondaire de l'espace Contacts (cf. ci-dessous) — plusieurs groupes possibles par membre |
| Modalité d'entraînement | Liste déroulante (nombre de jours d'entraînement/semaine) — **le tarif correspondant s'affiche automatiquement à côté** (source du montant de facturation, cf. section 5) |
| Jours d'entraînement | Sélecteur multiple parmi Lundi–Vendredi : les jours où la personne s'entraîne |

**Profil Majeur** (identique au profil mineur, sans les champs "responsables légaux" ; email alternative remplace les emails parents)

| Champ | Détail |
|---|---|
| Titre | Liste déroulante : Monsieur, Madame, Famille, Aux parents de |
| Prénom, Nom | Texte |
| Adresse | Texte |
| Code postal, Ville, Pays | Pays = liste déroulante |
| Sexe | Liste déroulante |
| Entrée, Sortie, Statut | Dates + statut en liste déroulante : Actif, Licence uniquement, Essai |
| ID, Rôle | ID = généré automatiquement (`prenom.nom`) ; Rôles = **plusieurs rôles possibles** : on choisit dans une liste (Tireur-euse, Coach, Maître d'arme, Membre, Comité, Président-e, Vice-président-e, Trésorier-ère, Secrétaire, Vérificateur des comptes) et chaque rôle retenu s'affiche en dessous sous forme de badge que l'on peut retirer (×) |
| N° AVS | Texte (format numéro AVS suisse) |
| Latéralité | Liste déroulante (ex. Droite/Gauche) |
| N° de licence | Texte |
| Téléphone escrimeur.euse | Texte |
| Email | Email |
| Email alternative | Email |
| Date de naissance | Date |
| Catégorie | **Calculée automatiquement** à partir de la date de naissance : U8, U10, U12, U14, U17, U20, Sénior, Vétéran |
| Nationalité | Liste déroulante |
| Groupe | Groupe secondaire de l'espace Contacts — plusieurs groupes possibles par membre |
| Modalité d'entraînement | Liste déroulante (nombre de jours d'entraînement/semaine) — **le tarif correspondant s'affiche automatiquement à côté** (source du montant de facturation, cf. section 5) |
| Jours d'entraînement | Sélecteur multiple parmi Lundi–Vendredi : les jours où la personne s'entraîne |

**Cours d'essai** (fiche allégée — pas d'AVS, licence, latéralité, rôle ni catégorie ; statut figé sur "Essai")

| Champ | Détail |
|---|---|
| Titre | Liste déroulante : Monsieur, Madame, Famille, Aux parents de |
| Prénom, Nom | Texte |
| Adresse | Texte |
| Code postal, Ville, Pays | Pays = liste déroulante |
| Sexe | Liste déroulante |
| Statut | Figé sur "Essai" (parmi la même liste : Actif, Licence uniquement, Essai) |
| ID | Généré automatiquement (`prenom.nom`) |
| Téléphone escrimeur.euse | Texte |
| Email | Email |
| Date de naissance | Date |
| Nationalité | Liste déroulante |
| Groupe | Groupe secondaire de l'espace Contacts |

Champs calculés/automatiques à implémenter : génération de l'ID (`prenom.nom`, avec gestion des doublons homonymes à prévoir), calcul de la catégorie d'âge à partir de la date de naissance pour les profils Mineur/Majeur (à revoir chaque saison, puisque l'âge change).

**Implémenté (19.09.2026) :** ID = `prenom.nom` en minuscules sans accents, homonymes suffixés `prenom.nom2`, `prenom.nom3`… Catégorie = âge atteint dans l'année civile de **fin de saison** (saison démarrant au mois configuré dans Paramètres du club, septembre par défaut) : U8 (<8), U10 (<10), U12 (<12), U14 (<14), U17 (<17), U20 (<20), Sénior (20-39), Vétéran (≥40). **À confirmer avec Alex** par rapport au règlement Swiss Fencing. Les catégories fixes de la liste sont définies ainsi : Personnes = tous les contacts non-entreprises ; Membres = statut Actif, Licence uniquement ou Essai ; Non-membres = autres statuts (en attente, inactif/sorti) ; Entreprises = contacts de type entreprise (sponsors…). Un statut « En attente de validation » et un statut « Inactif / sorti » ont été ajoutés à la liste Actif / Licence uniquement / Essai pour couvrir le flux d'inscription et les départs.

**Décision — passage d'un profil à l'autre :**
- **Essai → Mineur/Majeur** (essai concluant) : la personne remplit le formulaire d'inscription définitive ; sa fiche "Essai" est **supprimée** et une nouvelle fiche est créée de zéro à partir de cette nouvelle soumission (pas de fusion/migration de données).
- **Mineur → Majeur** (passage à la majorité) : **on ne change rien à la fiche.** Elle garde son jeu de champs "Mineur" (y compris les contacts parents) tel quel ; pas de conversion automatique de la structure de champs à 18 ans. Seule la Catégorie (U8/U10/.../Sénior) continue d'être recalculée automatiquement selon l'âge.

### Modèle des fiches modifiable (« Modèle des fiches membres »)

**Décision (19.09.2026, demande d'Alex) :** le comité peut éditer le format de chaque type de fiche (Mineur, Majeur, Essai) depuis Paramètres du club → « Modèle des fiches membres ». Chaque profil a son propre modèle, indépendant des autres. Pour chaque champ : **libellé affiché**, **section** (Identité et adresse, Adhésion, Contact, Escrime, Entraînement, Finance, Divers, Champs personnalisés), **position** dans la section (▲ ▼), **présence sur la fiche** de ce profil et caractère **sensible**. Les champs personnalisés (texte, liste, dates, jours de la semaine…) se créent depuis le même écran. Garde-fous : Prénom, Nom et Statut ne peuvent pas être masqués ; le N° AVS reste toujours sensible ; un bouton rétablit le modèle d'origine d'un profil. Les formulaires d'inscription, les colonnes de liste, les filtres et les exports suivent automatiquement (une seule source de vérité, cf. section 7). Le numéro de licence, le statut, la tranche tarifaire, la réduction famille, le rôle et les remarques internes restent réservés au comité : ils ne sont jamais proposés dans un formulaire public.

### Validation des inscriptions

**Décision : les soumissions de formulaire sont validées par le comité avant que le membre ne devienne actif.** *Implémenté (19.09.2026) :* le bouton « Valider l'inscription » de la fiche ouvre une fenêtre où le comité choisit la **tranche tarifaire**, confirme la **modalité d'entraînement**, coche la **réduction famille** si besoin et fixe la date d'entrée ; le montant de la cotisation s'affiche en direct, puis la fiche passe à « Actif » en une seule étape (un cours d'essai passe simplement à « Essai »). (Ça répond aux questions ouvertes correspondantes dans cette section et dans la section 7 — une soumission crée une fiche avec un statut "en attente de validation", pas directement "Actif".)

### Interface de la liste des contacts (référence : capture d'écran ClubDesk fournie)

On reprend une organisation proche de l'existant, avec une colonne latérale de catégories/groupes et une liste principale filtrable :

**Catégories principales (fixes, panneau de gauche, en haut) :**
- Tous les contacts
- Personnes
- Membres
- Non-membres
- Entreprises

**Groupes (panneau de gauche, en dessous, librement créés par le comité) :**
- Un groupe par cours (5 groupes, correspondant aux créneaux/modalités de cours du club).
- Un groupe "Essais".
- Un groupe "Comité".
- (Extensible à d'autres groupes ad hoc, ex. sponsors, comme dans l'exemple ClubDesk.)

**Comportement attendu :**
- Cliquer sur une catégorie ou un groupe affiche la liste des contacts correspondants dans le panneau principal.
- Un champ de recherche (par nom, a minima) permet de retrouver rapidement un contact.
- Au-dessus de la liste, un sélecteur de colonnes permet de choisir **quels champs de la fiche membre afficher** (y compris les champs personnalisés) et **dans quel ordre**, de façon à pouvoir par exemple afficher directement "facture envoyée / payée" en colonne pour un coup d'œil rapide sur tout un groupe.
- Actions de liste utiles à conserver (vues dans ClubDesk) : créer un nouveau contact, ouvrir/modifier une fiche, import/export, modification de masse.
- **Colonne « Statut de la facture » (19.09.2026, demande d'Alex) :** parmi les colonnes choisissables de la liste, elle affiche pour chaque membre l'état de sa facture de cotisation de la **saison en cours** sous forme de pastille colorée : Aucune facture, Générée (non envoyée), Envoyée, Relancée, Payée (une facture annulée, une facture d'une ancienne saison ou une facture manuelle ne comptent pas). Elle est aussi filtrable (« qui a payé ? », « à qui la facture a-t-elle été envoyée ? »).
- **Créer une liste de diffusion depuis la sélection (19.09.2026, demande d'Alex) :** après avoir coché des lignes, le bouton « Créer une liste de diffusion » demande un nom (proposé automatiquement) et crée une liste **statique** contenant ces contacts, immédiatement utilisable pour un email groupé ou la facturation groupée (section 8). Les contacts sans adresse email sont signalés : ils ne recevront rien.

### Points encore ouverts
- Colonnes par défaut de la vue liste : **Nom, Prénom, Adresse** (décidé). D'autres colonnes pourront être ajoutées/réordonnées librement par chacun depuis l'UI (cf. section "Interface de la liste").

## 5. Module Comptabilité / Facturation

### Problèmes actuels avec ClubDesk
- Seule la **génération groupée** des factures est possible, pas l'**envoi groupé** → envoi facture par facture, très long.
- Impossible de mettre le trésorier en copie de l'email d'envoi sans qu'une facture lui soit générée à lui aussi.
- Le montant de la facture doit être saisi/vérifié manuellement plutôt que déduit automatiquement de la modalité de cours choisie par le membre.

### Fonctionnalités souhaitées
- **Génération ET envoi groupés des factures**, en un seul flux.
- **Mise en copie (Cc/Bcc)** d'une adresse (ex. trésorier) sur les emails d'envoi de factures, sans effet secondaire sur la facturation elle-même.
- **Calcul automatique du montant** de la cotisation/facture à partir de la modalité de cours choisie par le membre (barème associé à chaque modalité/catégorie). Mécanisme précisé en section 4 : le champ "Modalité d'entraînement" sur la fiche membre (Mineur/Majeur) affiche déjà le tarif correspondant — c'est ce tarif qui alimente le montant de la facture générée.
- QR-facture suisse (comme évoqué précédemment) — à confirmer comme priorité.
- Suivi de statut par facture (envoyée / payée / en retard) et relances — à détailler avec le comité si souhaité dès la V1 ou plus tard.

### Génération technique des QR-factures

Bonne nouvelle : **pas besoin d'un logiciel externe ni d'un abonnement tiers.** La QR-facture suisse est une **norme ouverte et documentée** (spécification publiée par SIX, l'organisme qui gère les paiements interbancaires en Suisse). Concrètement, une QR-facture, c'est :

1. Un jeu de données standardisé : IBAN (ou QR-IBAN) du créancier (le club), son nom/adresse, le montant, la devise, l'adresse du débiteur (le membre), et un numéro de référence.
2. Ces données sont encodées dans un **QR-code** selon un format précis défini par la norme.
3. Un **gabarit visuel standardisé** (bloc de paiement + zone perforée) dans lequel ce QR-code et les informations lisibles sont placés, pour que la facture soit reconnue par n'importe quelle banque/appli suisse qui scanne le code.

Il existe des **bibliothèques open source et gratuites** qui génèrent directement ce PDF/SVG conforme à la norme à partir de ces données — je l'ai déjà testé (librairie Python `qrbill`) et ça fonctionne bien pour produire une QR-facture correcte. Donc : notre propre logiciel génère les QR-factures lui-même, en interne, sans dépendre d'un service tiers payant. Il faudra simplement, à la toute fin comme tu le prévois, lui donner les coordonnées bancaires du club (IBAN ou QR-IBAN, nom, adresse) — en attendant, on développera avec des données bancaires factices/placeholder.

**Décision — suivi des paiements reçus (V1) :** validation **manuelle** par le comité. Dans la liste des factures en attente (module Comptabilité + widget du tableau de bord, section 3), chaque ligne a une **case à cocher "payée"** : le comité (typiquement le trésorier) la coche après avoir constaté le paiement sur le relevé bancaire. Cocher la case passe le statut de la facture à "Payée", la retire de la liste des impayés et arrête le cycle de relances (section "Relances de paiement" ci-dessous). *(Piste pour une V2 seulement, pas pour maintenant : automatiser ce pointage par import d'un fichier `camt.053` exporté de la banque, pour rapprocher les paiements via le numéro de référence QR sans passer par le tiers payant — laissé de côté volontairement pour la V1.)*

### Spécifications techniques du module de facturation (à l'intention de Fable 5)

Cette section est écrite pour être directement exploitable au moment de coder le module — la qualité visuelle et la conformité de la facture sont importantes puisqu'elle est envoyée telle quelle aux membres.

**Norme à respecter :** la "Swiss Implementation Guidelines QR-bill", publiée par SIX (l'organisme suisse de clearing interbancaire) — c'est LA spécification officielle et publique de la QR-facture suisse (mise en page, encodage du QR-code, règles de validation des champs). Le module doit produire des factures strictement conformes à cette norme, pas une imitation approximative.

**Ne pas réinventer l'encodage/la mise en page à la main.** Utiliser une bibliothèque open source déjà conforme à la norme plutôt que de redessiner le gabarit QR-bill soi-même (le rendu du bloc de paiement, la position et le format du QR-code sont strictement normalisés — la moindre erreur de mise en page rend la facture invalide pour les banques/apps qui la scannent). Bibliothèques de référence déjà conformes et maintenues, à utiliser selon la stack retenue (section 11 "Choix techniques") :
- Python : [`qrbill`](https://pypi.org/project/qrbill/) — testé, génère directement un PDF/SVG conforme.
- Node.js/JavaScript : `swissqrbill`.
- .NET : `SwissQRBill.NET`.

**Données nécessaires pour générer une facture :**
- **Créancier (le club)** : nom, adresse structurée (rue, n°, NPA, ville, pays), IBAN ou QR-IBAN — ces coordonnées seront fournies par Alex à la fin du développement ; utiliser des valeurs fictives/placeholder en attendant, clairement identifiables comme telles dans la configuration (pas codées en dur dans plusieurs endroits — un seul point de configuration central pour ces coordonnées, facile à remplacer).
- **Débiteur (le membre)** : nom, prénom, adresse — directement repris de la fiche membre (section 4).
- **Montant et devise** : CHF, calculé automatiquement à partir de la modalité d'entraînement + tranche tarifaire (barème ci-dessous).
- **Numéro de référence** : généré automatiquement par la bibliothèque selon le type de référence correspondant au compte du club (référence QR si QR-IBAN) — ne jamais construire ce numéro à la main, la bibliothèque calcule le chiffre de contrôle correctement.
- **Informations complémentaires / motif du paiement** : doit indiquer clairement à quoi correspond la facture (ex. "Cotisation saison 2026-2027 — [Prénom Nom] — Modalité [X]") pour que ce soit lisible autant par le membre que par le club au moment du rapprochement.

**Mise en page professionnelle attendue :**
- Un document PDF avec, en haut, un en-tête présentable du club (nom, logo si disponible, adresse, éventuellement IBAN visible aussi en texte), le numéro de facture, la date d'émission et la date d'échéance, le détail de la prestation facturée (membre, saison, modalité, montant) — puis, en bas de page, le bloc QR-bill généré par la bibliothèque, sans modification de sa mise en page normalisée.
- Langue : français (paramètre de langue de la bibliothèque à régler sur `fr`).
- Le PDF généré est ce qui est joint aux emails envoyés en masse (section "Fonctionnalités souhaitées" ci-dessus).

**Vérification qualité :** avant de considérer le module terminé, valider un exemplaire de facture générée avec l'outil de validation en ligne officiel de SIX pour les QR-factures, afin de confirmer sa conformité totale à la norme (et pas seulement une conformité visuelle approximative).

*État (19.09.2026) :* le portail SIX (https://validation.iso-payments.ch) exige un compte utilisateur — **à faire par Alex** avec le fichier `docs/exemples/exemple-qr-facture.pdf`. Un contrôle automatique local (`python manage.py check_qrbill`) décode le QR code du PDF réellement généré et vérifie son contenu contre les directives (version 2.3 : adresses structurées obligatoires, référence QR/SCOR valide, taille 46 mm et position du QR) ; il passe. Référence de paiement : référence QR (27 chiffres, chiffre de contrôle calculé par `python-stdnum`) avec un QR-IBAN, référence SCOR ISO 11649 avec un IBAN classique — détection automatique selon l'IBAN saisi dans Paramètres du club.

**Archivage automatique :** chaque facture générée est produite en **PDF** et une **copie est automatiquement déposée dans l'espace de stockage de fichiers** (section 6), dans un sous-dossier dédié (ex. `Club/Factures/2026-2027/...`), pour garder une trace consultable de toutes les factures émises — sur le même principe que l'archivage prévu pour les soumissions de formulaire (section 6).

### Barème des cotisations

Structure du barème : **3 modalités d'entraînement** (nombre de jours/semaine — cf. champ "Modalité d'entraînement" en section 4), chacune déclinée en **4 tranches tarifaires** :
- P'tit Zorros
- Moins de 20 ans
- Dès 20 ans
- Étudiant entre 20 et 25 ans

Soit une grille de 3 × 4 = 12 tarifs à définir (montants pas encore fixés — Alex les communiquera).

**Réduction famille :** -100 CHF sur la cotisation à partir du 2ᵉ enfant inscrit d'une même famille (donc le 1er enfant paie plein tarif, le 2ᵉ et les suivants bénéficient de -100 CHF chacun).

**Simplification décidée :** dans le formulaire d'inscription en ligne, la personne ne choisit que la **modalité d'entraînement** et les **jours** (section 4/7). La tranche tarifaire (P'tit Zorros / moins de 20 ans / dès 20 ans / étudiant 20-25 ans), le statut étudiant, et le fait qu'il s'agisse d'un 2ᵉ enfant (ou plus) de la famille sont **complétés manuellement par le comité au moment de la validation de l'inscription** (cf. section 4 "Validation des inscriptions"). Pas de champ "Statut étudiant" ni de lien "famille" automatique à implémenter pour la V1 : c'est le comité qui juge et coche/sélectionne ces informations sur la fiche avant validation.

### Relances de paiement

**Décision :** relance automatique envoyée si une facture n'a pas été payée **1 mois après sa date d'édition**. (À affiner : un seul niveau de relance pour l'instant, ou plusieurs relances espacées comme évoqué dans les logiciels concurrents ? — cf. points ouverts.)

*Implémenté (19.09.2026) :* un seul niveau de relance, **répété tous les 30 jours** (délai réglable dans Paramètres du club) tant que la facture reste impayée, uniquement pour les factures déjà envoyées. Envoi par la commande planifiée `send_reminders` ou par le bouton « Envoyer » du module Comptabilité. Le trésorier est en Cc des relances comme des factures. Texte de relance modifiable dans Paramètres du club.

### Facture manuelle indépendante

**Décision (19.09.2026, demande d'Alex) :** en plus des cotisations calculées depuis la fiche, le comité peut créer **une facture isolée à la main** (bouton « Facture manuelle » dans Comptabilité, la liste des factures et la fiche d'un contact) : choix du **destinataire** parmi les contacts (personne ou entreprise), **montant** en CHF, **motif** (140 caractères, repris dans la QR-facture), date d'émission, échéance et email d'envoi facultatif. Elle suit exactement le même circuit que les autres factures : même série de numéros, référence de paiement calculée, PDF avec QR-facture, archivage dans `Club/Factures/<saison>`, envoi avec le trésorier en Cc, relances, pointage du paiement. Elle n'entre pas dans la règle « une facture par membre et par saison » : un contact peut recevoir plusieurs factures manuelles.

### Périmètre de la comptabilité

**Décision :** pour la V1, le module Comptabilité se limite **uniquement aux cotisations** (facturation, suivi, relances). Pas d'autres types de recettes/dépenses du club pour l'instant. *Précision (19.09.2026) :* la facture manuelle ci-dessus reste une facture émise au nom du club avec le même suivi ; elle ne crée ni comptabilité des dépenses ni autres recettes.

### Points encore ouverts
- Montants exacts des 12 tarifs (3 modalités × 4 tranches).
- Un seul niveau de relance à 1 mois, ou plusieurs relances espacées (ex. rappel à 1 mois, mise en demeure à 2 mois) ?
- Qui reçoit une copie/notification quand une relance automatique part (le trésorier) ?

## 6. Espace Stockage de fichiers

### Fonctionnement actuel (à conserver)
- Un simple explorateur de fichiers avec (au moins) trois dossiers : **Club**, **Direction**, **Public**.
- Sert à ranger les documents administratifs du club en général.
- C'est aussi là qu'atterrissent aujourd'hui les formulaires d'inscription remplis par les gens (le formulaire rempli en lui-même est stocké comme fichier, pas des pièces jointes fournies par l'inscrit).

### Pour la V1
- Reproduire cet explorateur simple (dossiers/sous-dossiers, upload, téléchargement, suppression, renommage).
- Garder au minimum les 3 dossiers Club / Direction / Public, avec la possibilité d'en créer d'autres.
- Question ouverte : une fois que les inscriptions passeront par le nouveau formulaire → fiche contact automatique (section 4), a-t-on encore besoin qu'un fichier "formulaire rempli" soit déposé ici, ou la fiche contact suffit-elle ? À trancher — on peut par exemple garder un export PDF automatique de chaque soumission déposé dans un sous-dossier dédié, pour garder une trace telle que remplie par la personne. *Implémenté en attendant (19.09.2026) :* chaque soumission est conservée telle que remplie dans le module Formulaires → « Soumissions reçues » (toutes les réponses), en plus de l'email au secrétariat ; aucun fichier par soumission n'est déposé dans l'explorateur. Les modèles de formulaires y sont en revanche copiés (JSON) dans `Club/Formulaires`.
- **Décidé :** chaque facture générée (PDF, section 5) est automatiquement archivée ici dans un sous-dossier dédié — voir section 5 "Archivage automatique".

## 7. Module Formulaires (inscription et autres)

### Ce que tu veux pouvoir faire
- Créer plusieurs formulaires différents (inscription complète, cours d'essai, éventuellement autre chose).
- Formulaire **entièrement personnalisable** :
  - Zones de texte libres pour expliquer/contextualiser.
  - Champs à remplir, dans l'ordre choisi.
  - Plusieurs types de champ : texte, date, liste déroulante personnalisable, sélecteur de jour(s) de la semaine, etc.
  - **Logique conditionnelle** à la Google Forms : faire apparaître des champs supplémentaires selon une réponse donnée (ex. cocher "mineur" fait apparaître les champs du/des responsable(s) légal/légaux).
  - Les noms des champs du formulaire doivent être **exactement les mêmes** que ceux de la fiche membre correspondante, pour ne jamais avoir de décalage entre les deux.

### Comment ça marche techniquement (explication)

Un formulaire en ligne, concrètement, c'est trois choses séparées :

1. **La définition du formulaire** : la liste des champs, leur type, leur ordre, et les règles d'affichage conditionnel. C'est une donnée structurée (pas du code), qui peut être stockée en base et modifiée sans redéployer l'application.
2. **La page publique** qui affiche ce formulaire à quelqu'un qui n'est pas connecté au logiciel (un parent, un nouvel inscrit) et qui envoie les réponses au serveur quand la personne valide.
3. **Le traitement de la soumission** : que fait-on des réponses reçues ? Dans notre cas → créer/mettre à jour automatiquement une fiche contact avec ces données (section 4), avec éventuellement une étape de validation par le comité avant que le membre soit "actif".

Trois façons de construire le point 1 (la définition du formulaire), du plus simple au plus riche à développer :

- **A. Formulaires codés en dur** : chaque formulaire est écrit directement dans le code de l'application. Rapide à obtenir pour un premier formulaire, mais chaque modification demande de repasser par du code (donc par moi/Fable 5). Aucune autonomie ensuite pour le comité.
- **B. Éditeur structuré (retenu pour la V1)** : dans l'application, un écran permet d'ajouter/retirer/réordonner des champs, de choisir leur type dans une liste (texte, date, liste déroulante, sélecteur de jour, etc.), de définir des règles simples ("afficher le champ X si le champ Y = telle valeur"). Ce n'est pas un glisser-déposer visuel comme Google Forms, mais une liste de champs configurables — nettement plus rapide à construire qu'un éditeur visuel complet, tout en donnant une vraie autonomie au comité. Comme cette liste de champs EST la même structure que la fiche membre, on garantit par construction que formulaire et fiche membre restent synchronisés.
- **C. Éditeur visuel complet (à la Google Forms)** : glisser-déposer, aperçu en direct pendant la création. Plus agréable à utiliser mais beaucoup plus long à développer (c'est essentiellement reconstruire un petit Google Forms) — écarté pour la V1, à envisager comme évolution future si l'éditeur structuré s'avère trop limité en pratique.

**Décision retenue : option B (éditeur structuré)** pour la V1.

### Comment le formulaire est rendu accessible (hébergement du lien)

Deux façons de faire, indépendantes du choix ci-dessus :

- **Lien public direct** : le logiciel génère une page web publique (sans connexion nécessaire) à une adresse dédiée pour chaque formulaire (ex. `.../inscription/loisir`). On met simplement ce lien sur le site du club, exactement comme le lien ClubDesk actuel est probablement fait. C'est l'option la plus simple, et celle qui reproduit ce qui existe déjà.
- **Intégration (iframe) dans le site du club** : si la plateforme du site web du club le permet, on peut afficher cette même page publique directement encastrée dans une page du site, sans que le visiteur ne voie qu'il s'agit d'un autre système. Plus intégré visuellement, mais dépend de ce que permet l'outil de site web du club.

Ces deux options utilisent la même page publique générée par notre logiciel ; la différence est juste "lien cliquable" vs "encastré dans une page existante". **Point à vérifier de ton côté** : regarde comment le lien du formulaire ClubDesk actuel est intégré sur le site du club (clic droit sur le bouton/lien du formulaire → "copier le lien", ou inspection de la page) pour savoir si c'est un simple lien ou déjà une iframe — cela dira si on peut reproduire à l'identique avec un simple lien public.

**Décision (19.09.2026, 2ᵉ série, demande d'Alex) :** le champ **Titre** (Monsieur, Madame, Famille, Aux parents de) n'est plus demandé dans les formulaires publics : le comité le complète sur la fiche si besoin. À l'inverse, la personne peut **choisir son ou ses groupes** (typiquement son créneau de cours) : seuls les groupes marqués « Proposé dans les formulaires d'inscription » (case dans la gestion des groupes, cochée par défaut pour les groupes de cours) sont offerts, jamais les groupes internes comme « Comité » ; elle s'ajoute aux groupes attribués automatiquement par le formulaire. Si aucun groupe n'est proposé, le champ disparaît du formulaire.

**Décision (19.09.2026, demande d'Alex) :** le **numéro de licence** n'est plus demandé dans les formulaires publics (il est attribué par le club/la fédération et reste sur la fiche, à compléter par le comité). Le champ « Téléphone élève » s'appelle désormais « **Téléphone escrimeur.euse** » partout (fiche et formulaires, l'ancien libellé reste reconnu à l'import CSV).

### Types de champs de l'éditeur

**Décision :** l'éditeur doit proposer tous les types de champs nécessaires pour remplir n'importe quel champ des fiches membres (section 4), plus des zones de texte libre (non-input) pour les explications/consignes. Concrètement, au vu des champs listés en section 4, l'éditeur doit couvrir au minimum :
- Texte court (ex. Prénom, Nom, Adresse, N° AVS, N° de licence, téléphones)
- Liste déroulante personnalisable à choix unique (ex. Titre, Sexe, Pays, Nationalité, Latéralité, Modalité d'entraînement)
- Sélecteur multiple (ex. Jours d'entraînement, Lundi–Vendredi)
- Date (ex. Date de naissance)
- Email
- Zone de texte libre / bloc explicatif (non-input, pour contextualiser une section du formulaire)
- Logique conditionnelle d'affichage entre champs (section 4bis, ex. mineur → champs responsables légaux)

### Stockage et accès

- **Création** : les formulaires sont créés et gérés entièrement depuis notre logiciel (éditeur structuré, section précédente).
- **Stockage du modèle** : le modèle de formulaire est conservé dans notre espace de stockage de fichiers (section 6), aux côtés des autres documents administratifs du club. *(Note technique : pour fonctionner — affichage dynamique, validation, champs conditionnels — le formulaire doit aussi exister sous forme de donnée structurée exploitable par l'application ; on prévoira que la version "fichier" dans l'explorateur soit une copie/export de référence de ce modèle, et pas l'unique source utilisée par le formulaire en ligne.)*
- **Accès** : chaque formulaire est exposé via un **lien public** posté sur le site web du club — comme c'est déjà le cas aujourd'hui (option "lien direct" retenue, cf. ci-dessus).

### Notification à la soumission

**Décision :** à chaque soumission d'un formulaire d'inscription, un **email récapitulatif est envoyé à la boîte mail du secrétariat du club**, comme c'est le cas actuellement avec ClubDesk — en plus de la création de la fiche "en attente de validation" (section 4).

**Décision :** le récapitulatif envoyé par email contient **toutes les réponses** de la soumission (pas un résumé partiel).

*Implémenté (19.09.2026) :* règle de validation ajoutée côté serveur — au moins une adresse email (élève, parent ou alternative) est exigée dans toute soumission comportant un champ email, pour pouvoir envoyer confirmations et factures. Pour un mineur, le téléphone et l'email du parent 1 sont obligatoires par défaut (modifiable dans l'éditeur). Anti-spam : champ piège invisible + rejet des soumissions envoyées moins de 3 secondes après l'affichage.

### Comparaison avec le fonctionnement de ClubDesk

Pour vérifier que notre approche est réaliste et voir si on peut faire mieux, voici comment ClubDesk gère concrètement ses formulaires (documentation officielle + forum ClubDesk) :

- **Création** : éditeur par blocs, avec 10 types de champs (texte, texte multi-lignes, email, date/heure, nombre, oui/non, liste déroulante simple/multiple, titre/section, séparateur). Le formulaire est inséré comme un bloc sur une page du site web du club (site hébergé par ClubDesk).
- **Réception des données** : chaque soumission est stockée comme une ligne dans un tableau à part — **pas directement comme fiche contact**.
- **Le point faible confirmé** : pour faire passer ces données dans le module Contacts, il faut **exporter le tableau en CSV, corriger/dédoublonner à la main dans un tableur, puis ré-importer** en vérifiant le mapping des colonnes. Aucune synchronisation automatique formulaire → fiche contact. C'est exactement le problème de recopie manuelle que tu decrivais en section 4.
- Rien dans leur documentation n'indique de logique conditionnelle (afficher un champ selon la réponse à un autre) ni de sélecteur dédié "jours de la semaine" — on reste sur des cases à cocher/listes déroulantes génériques pour ça.

**Conclusion :** ce qu'on prévoit déjà (section 7 : éditeur structuré + création automatique de la fiche contact en attente de validation, section 4) est tout à fait réalisable — c'est le même principe de blocs/types de champs que ClubDesk, avec la même liste de types de champs somme toute (texte, date, liste déroulante, sélection multiple, etc.), sauf qu'on **supprime l'étape manuelle export CSV → tableur → import**, qui est justement le plus gros point de friction que tu avais identifié. On ajoute aussi la logique conditionnelle (visible nulle part chez ClubDesk), qui est un vrai plus. Rien à changer au plan actuel : il confirme et dépasse déjà ce que fait ClubDesk sur ce point précis.

### Points encore ouverts
- Adresse exacte de la boîte mail du secrétariat à utiliser pour ces notifications (à confirmer, probablement `secretariat@escrime-founex.ch` d'après la fiche membre vue précédemment).

## 8. Module Mailing groupé

### Besoin

Deux fonctionnalités principales :

1. **Listes de diffusion**, constituées soit automatiquement à partir d'un **groupe secondaire de l'espace Contacts** (section 4 — ex. tous les membres du groupe "19h15-21h00", ou tous les "Essais"), soit **créées manuellement** en sélectionnant des contacts un par un (indépendamment des groupes existants).
2. **Envoi groupé des factures** (résout le problème principal identifié en section 5 : ClubDesk ne permet que la génération groupée, pas l'envoi groupé).

### Listes de diffusion

*Ajout (19.09.2026) :* une liste statique peut aussi être créée en un clic depuis la liste des Contacts, à partir des lignes cochées (bouton « Créer une liste de diffusion », section 4).

- Une liste peut être **dynamique** (= "tous les membres du groupe X", se met à jour automatiquement si le groupe change) ou **statique** (= une sélection figée de contacts choisie manuellement, qui ne bouge pas si les groupes changent ensuite).
- Utilisées aussi bien pour de simples emails groupés (annonces, infos) que comme base pour la génération/l'envoi de factures groupées.

### Génération + envoi groupé des factures : méthode proposée

Tu me laisses proposer la meilleure méthode — voici ce que je recommande, avec le raisonnement :

**En deux étapes distinctes (génération, puis envoi), et non en une seule manipulation.** Raisons :
- Ça permet un **contrôle avant envoi** : après génération groupée, le comité peut parcourir/vérifier les factures produites (montants, destinataires) avant qu'elles ne partent réellement aux membres — évite d'envoyer une erreur à 60 personnes d'un coup.
- Ça correspond à un flux de travail réaliste : on peut générer un lundi, relire tranquillement, et envoyer le mardi une fois que tout est vérifié.
- Techniquement, ça reste très simple à enchaîner : "Générer" produit toutes les factures (PDF + archivage automatique, section 5) pour la liste sélectionnée ; un bouton "Envoyer" séparé (mais accessible directement depuis le même écran, à la suite) déclenche l'envoi groupé de tout ce qui vient d'être généré — donc dans la pratique, ça peut se faire en quelques clics à la suite si le comité veut aller vite, sans que ce soit une seule action irréversible.

**Déroulé concret du flux :**
1. Le comité choisit une **liste de diffusion** (groupe existant ou liste manuelle).
2. Le logiciel récupère, pour chaque membre de la liste, les données nécessaires depuis sa **fiche membre** (section 4) : nom, adresse (débiteur de la QR-facture), email (destinataire), modalité d'entraînement + tranche tarifaire (montant, section 5).
3. **Génération groupée** : une facture PDF est créée pour chaque membre de la liste, archivée automatiquement (section 5/6). Le comité voit un récapitulatif (qui a été facturé, quel montant) avant envoi.
4. **Envoi groupé** : un email est envoyé à chaque membre de la liste avec sa facture PDF en pièce jointe, en une seule action pour toute la liste (résout le problème "facture par facture" de ClubDesk).
5. **Décision confirmée :** l'adresse du **trésorier** est mise en **copie (Cc)** sur chaque email d'envoi de facture (individuel comme groupé), sans que ça ne génère de facture supplémentaire pour cette adresse (répond au problème identifié en section 5). L'adresse du trésorier est configurée **une seule fois dans les paramètres du club** (avec les coordonnées bancaires, section 5), pas ressaisie à chaque envoi — cohérent avec le principe d'un point de configuration central.

### Points encore ouverts
- Contenu/modèle du texte de l'email d'envoi de facture (fixe, ou personnalisable par le comité à chaque envoi ?). *Implémenté en attendant :* modèle unique modifiable dans Paramètres du club (variables `{prenom}`, `{nom}`, `{saison}`, `{modalite}`, `{montant}`, `{echeance}`, `{numero}`), pas de personnalisation à chaque envoi.
- Faut-il pouvoir exclure certains membres d'une liste au moment de l'envoi (sans les retirer du groupe), pour un cas exceptionnel ? *Implémenté :* oui — cases à décocher à l'étape d'envoi (factures comme emails groupés), et option « ignorer les membres déjà facturés pour la saison » à la génération.

## 9. Module Inscriptions

(Recoupe largement le module Contacts, cf. section 4 — le formulaire d'inscription en ligne EST le point d'entrée du module Contacts.)

- Un même mécanisme de formulaire doit couvrir : inscription complète (nouveau membre à l'année), inscription à un cours d'essai (fiche allégée).
- *(Un formulaire séparé pour les événements ponctuels — compétitions, stages — est écarté pour l'instant, pas prioritaire pour la V1.)*

## 10. Export de données

### Besoin
- Export simple en **CSV** des données de contacts (et, par le même mécanisme, de la comptabilité), pour éviter le copier-coller manuel actuel.
- *(Export compatible Jeunesse+Sport écarté pour l'instant — pas prioritaire pour la V1.)*

### Fonctionnement dans l'espace Contacts

1. Dans la liste des contacts (section 4), le comité peut **sélectionner une ou plusieurs lignes** (cases à cocher sur les lignes, ou sélection multiple classique).
2. Un bouton "Exporter" ouvre un choix de **colonnes à inclure** :
   - **Toutes les colonnes** de la fiche membre.
   - **Colonnes remplies** : uniquement les colonnes qui ont au moins une valeur renseignée parmi les lignes sélectionnées (évite les colonnes vides inutiles dans l'export).
   - **Colonnes à choix** : une liste déroulante avec une **case à cocher par colonne disponible**, pour sélectionner librement lesquelles inclure. *(Tu as parlé de "boutons radios" — comme il faut pouvoir cocher plusieurs colonnes à la fois, on part sur des cases à cocher dans cette liste déroulante plutôt que des radios, qui n'autorisent qu'un seul choix. Dis-moi si tu avais autre chose en tête.)*
3. Choix du **format d'export**, avec trois variantes de CSV proposées : **CSV Excel Windows/iOS/Android**, **CSV macOS**, **CSV Numbers**.

### Note technique sur les formats CSV (à l'intention de Fable 5)

Ces trois "formats" ne sont pas des fichiers fondamentalement différents (un CSV reste un CSV), mais des **variantes d'encodage/de mise en forme** attendues par défaut par chaque application au moment de l'ouverture — la principale différence pratique est que des caractères accentués (les noms/adresses du club en contiennent beaucoup : "Genève", "Café", etc.) peuvent s'afficher correctement dans une appli et être corrompus dans une autre si le mauvais export est utilisé. Points à gérer précisément à l'implémentation :
- **Séparateur de colonnes** : virgule `,` ou point-virgule `;` selon la convention régionale (Excel en français utilise souvent `;` car `,` est le séparateur décimal).
- **Encodage des caractères** : UTF-8 (avec ou sans BOM — le BOM aide Excel Windows à détecter l'UTF-8 correctement) vs d'autres encodages historiques.
- **Fin de ligne** : `\r\n` (Windows) vs `\n` (Unix/macOS moderne) vs `\r` seul (ancien Mac, obsolète mais parfois encore attendu par des exports "CSV Macintosh" historiques).

Fable 5 devra implémenter ces trois variantes avec les bons réglages (séparateur/encodage/fin de ligne) pour chacune, et tester l'ouverture du fichier exporté dans Excel (Windows), Numbers (Mac), et un tableur mobile pour confirmer que les accents s'affichent correctement dans chaque cas avant de considérer la fonctionnalité terminée.

**Décidé :** pas de colonnes calculées spécifiques nécessaires — le mécanisme générique de sélection de colonnes (ci-dessus) suffit pour les exports comptabilité comme contacts.

## 11. Choix techniques

### Séquencement développement local → hébergement

**Décision :** le développement se fait d'abord **entièrement en local** (sur l'ordinateur d'Alex), sans souscrire d'hébergement. L'abonnement à un hébergeur (section suivante) n'intervient qu'**une fois l'application testée et validée** par Alex/le comité. Conséquence pour Fable 5 : l'application doit pouvoir être installée et lancée facilement en local (base de données locale de développement, instructions d'installation claires), sans dépendance obligatoire à un service payant pour être testée de bout en bout — le passage à l'hébergement de production (section suivante) se fait dans un second temps, une fois l'IBAN/QR-IBAN du club également disponible (cf. section 5).

### Stack retenue

| Brique | Choix | Pourquoi |
|---|---|---|
| Langage / framework backend | **Python / Django** | Écosystème mature pour ce type d'application de gestion (comptes utilisateurs, permissions, formulaires, ORM relationnel), permet à Alex de comprendre/retoucher lui-même certaines parties du code sans dépendre uniquement de Fable 5. |
| Base de données | **PostgreSQL** | Base relationnelle gratuite et robuste, adaptée aux données structurées et reliées entre elles du projet (membres, groupes, factures, champs personnalisés). |
| Génération des QR-factures | Bibliothèque conforme à la norme suisse QR-bill (ex. `qrbill` pour Python) | Cf. section 5 — pas de service tiers payant, tout est généré en interne. |
| Hébergement | **Hébergeur basé en Suisse** (ex. Infomaniak) | Les données traitées (adresses, dates de naissance, N° AVS, données de mineurs) restent soumises au droit suisse de la protection des données (LPD) — plus approprié qu'un hébergeur étranger générique pour ce type de données. Coût attendu modeste pour un usage à l'échelle d'un club. |

### Exigences de sécurité et de protection des données (obligatoire — à l'intention de Fable 5)

Ce projet traite des données personnelles sensibles (dont celles de mineurs et des numéros AVS) : les points suivants ne sont **pas optionnels** et doivent être implémentés dès la V1, pas ajoutés "plus tard".

**Accès et authentification**
- Toute page/fonction de gestion (tout sauf les formulaires publics d'inscription, section 7) nécessite une **connexion utilisateur** — aucun accès anonyme à l'interface de gestion.
- Mots de passe : stockage **hashé** (jamais en clair — Django gère ça nativement, s'assurer que ce mécanisme par défaut n'est pas contourné), avec exigence de mot de passe robuste à la création d'un compte.
- **Authentification à deux facteurs (2FA/A2F) obligatoire** pour tous les comptes du comité (pas seulement recommandée) — cf. section 3 "Interface générale" pour le déroulé (configuration à l'inscription, saisie à chaque connexion).
- Session utilisateur expirée après une période d'inactivité raisonnable.

**Transport et infrastructure**
- **HTTPS obligatoire** sur l'intégralité du site (interface de gestion ET formulaires publics) — aucune page servie en HTTP simple, y compris en développement/test si possible.
- Secrets de configuration (mot de passe de la base de données, identifiants de la boîte mail du secrétariat, futures coordonnées bancaires, clé secrète Django) stockés en **variables d'environnement côté serveur**, jamais écrits en clair dans le code source ni committés dans un dépôt de code.

**Données sensibles spécifiques au projet**
- **Numéro AVS** (section 4) : champ à traiter comme sensible — non affiché par défaut dans les vues listes, accès à la valeur complète restreint aux fiches individuelles, **exclu par défaut** des exports (section 10) sauf sélection explicite de cette colonne par l'utilisateur.
- Données des **mineurs** (contacts parents, section 4) : mêmes règles d'accès que le reste — pas de champ public exposé sans authentification, en dehors du formulaire d'inscription lui-même qui les collecte.
- Le formulaire d'inscription public doit afficher une **mention courte** indiquant pourquoi ces données sont collectées et à quoi elles servent (obligation de transparence de base au sens de la LPD suisse).

**Disponibilité et intégrité des données**
- **Sauvegardes automatiques régulières** de la base de données (quotidiennes a minima), avec conservation d'un historique de quelques jours/semaines pour pouvoir restaurer en cas de problème.
- Fichiers de l'espace de stockage (section 6) et factures archivées (section 5) inclus dans le périmètre des sauvegardes, pas seulement la base de données.

**Protection des formulaires publics**
- Les formulaires d'inscription (section 7) sont accessibles sans connexion et donc exposés aux robots/spam : prévoir une protection simple et non intrusive (ex. champ "piège à robots" invisible — *honeypot* — plutôt qu'un captcha visible qui dégraderait l'expérience des vrais inscrits).
- Validation systématique côté serveur des données soumises (pas seulement côté navigateur), avant création d'une fiche "en attente de validation" (section 4).

**Bonnes pratiques générales attendues du développement (Fable 5)**
- Utiliser les mécanismes de sécurité **par défaut** de Django plutôt que de les réimplémenter à la main (protection CSRF, échappement automatique des données affichées pour éviter les injections, protection contre l'injection SQL via l'ORM) — ne pas contourner ces protections pour "simplifier" du code.
- Toute action de suppression définitive (ex. suppression d'une fiche "Essai" lors du passage à une fiche définitive, section 4) doit être une action explicite et confirmée, pas déclenchée par erreur en un clic.
