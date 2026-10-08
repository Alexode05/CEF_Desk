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

Ouvrir <http://127.0.0.1:8000/>, cliquer « Créer un compte » et saisir le code d'invitation. Un email de
vérification est envoyé : le compte s'active en cliquant sur le lien, puis la connexion se fait avec le nom
d'utilisateur (ou l'adresse email) et le mot de passe.

En local sans serveur email (`EMAIL_URL` vide, `DJANGO_DEBUG=True`), les emails ne partent pas : ils
s'affichent dans le terminal du serveur, et le lien de vérification (ou de nouveau mot de passe) est aussi
affiché directement sur la page. Ce raccourci n'existe jamais en production.

Pour créer un compte administrateur sans passer par l'inscription :

```bash
python manage.py createsuperuser
```

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
- Ne pas exposer le dossier `media/` (factures, documents) par le serveur web : ces fichiers ne doivent être
  téléchargés qu'à travers l'application, qui vérifie la connexion.
- La limitation des tentatives de connexion utilise le cache Django : avec plusieurs processus, configurer un
  cache partagé (ex. base de données ou Redis) pour qu'elle reste efficace.
- Remplacer les coordonnées bancaires placeholder et valider une facture sur le portail SIX avant tout envoi réel.
