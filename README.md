# CEF Desk

Logiciel de gestion du Cercle d'Escrime de Founex (remplacement de ClubDesk) : contacts/membres,
facturation avec QR-factures suisses, formulaires d'inscription en ligne, mailing groupé, stockage
de fichiers, exports CSV. Référence fonctionnelle : [`docs/cahier-des-charges.md`](docs/cahier-des-charges.md).

## Installation locale (Windows, macOS ou Linux)

Prérequis : Python 3.12+.

```bash
python -m venv .venv
# Windows : .venv\Scripts\activate    macOS/Linux : source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env               # (cp sur macOS/Linux) puis éditer .env
python manage.py migrate
python manage.py seed_reference_data  # champs, groupes, modalités, tranches, dossiers, paramètres
python manage.py runserver
```

Dans `.env`, définir au minimum `DJANGO_SECRET_KEY` (clé aléatoire longue) et `CEF_REGISTRATION_CODE`
(code d'invitation à communiquer aux membres du comité pour créer leur compte).

Ouvrir <http://127.0.0.1:8000/>, cliquer « Créer un compte », saisir le code d'invitation, puis
configurer l'authentification à deux facteurs avec une application type Google/Microsoft Authenticator.
L'A2F est obligatoire et demandée à chaque connexion.

## Premiers réglages après installation

1. **Paramètres du club** : coordonnées du club, IBAN/QR-IBAN (les valeurs livrées sont des
   placeholders fictifs, marqués `[PLACEHOLDER]`), email du trésorier (Cc des factures), email du
   secrétariat (notifications d'inscription), textes des emails.
2. **Comptabilité → Barème** : saisir les 12 tarifs (3 modalités × 4 tranches).
3. **Contacts → Groupes** : renommer les 5 groupes de cours.
4. **Formulaires** : créer « Inscription » (Mineur/Majeur) et « Cours d'essai », puis poser le lien public
   sur le site du club.

## Tâches planifiées (à mettre en place chez l'hébergeur ou via le Planificateur de tâches Windows)

```bash
python manage.py send_reminders   # quotidien : relances des factures impayées après le délai configuré
python manage.py backup           # quotidien : sauvegarde BD + fichiers dans backups/ (rétention 30 j)
```

## Contrôle qualité des QR-factures

```bash
pip install -r requirements-dev.txt
python manage.py check_qrbill            # décode le QR du dernier PDF généré et le vérifie contre la norme
```

La **validation finale sur le portail officiel SIX** (<https://validation.iso-payments.ch/>, compte gratuit
requis) doit être faite manuellement en y déposant un PDF généré, par exemple
[`docs/exemples/exemple-qr-facture.pdf`](docs/exemples/exemple-qr-facture.pdf).

## Tests

```bash
python manage.py test apps
```

## Production (plus tard)

- `DJANGO_DEBUG=False`, `DJANGO_FORCE_HTTPS=True`, `DJANGO_ALLOWED_HOSTS=domaine.ch`
- `DATABASE_URL=postgres://user:motdepasse@hote:5432/cefdesk` (PostgreSQL)
- `EMAIL_URL=smtp+tls://utilisateur:motdepasse@mail.infomaniak.com:587`
- `python manage.py collectstatic`, serveur WSGI (gunicorn/uwsgi) derrière un reverse proxy HTTPS.
- Remplacer les coordonnées bancaires placeholder et valider une facture sur le portail SIX avant tout envoi réel.
