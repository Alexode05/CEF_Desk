"""
Réglages Django de CEF Desk.

Tous les secrets proviennent de variables d'environnement (fichier `.env` local,
jamais committé) — cf. cahier des charges section 11.
"""
from pathlib import Path
import os
from urllib.parse import urlparse, unquote

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    value = env(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


# --- Sécurité de base ------------------------------------------------------

SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "DJANGO_SECRET_KEY manquante : copier .env.example vers .env et définir une clé secrète."
    )

DEBUG = env_bool("DJANGO_DEBUG", False)

ALLOWED_HOSTS = [
    h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()
]

# --- Applications -----------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Tiers
    "django_otp",
    "django_otp.plugins.otp_totp",
    "crispy_forms",
    "crispy_bootstrap5",
    # CEF Desk
    "apps.accounts",
    "apps.dashboard",
    "apps.members",
    "apps.billing",
    "apps.documents",
    "apps.formbuilder",
    "apps.mailing",
    "apps.exports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "apps.accounts.middleware.LoginAndTwoFactorRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "cefdesk.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.dashboard.context_processors.club_context",
            ],
        },
    },
]

WSGI_APPLICATION = "cefdesk.wsgi.application"

# --- Base de données --------------------------------------------------------
# SQLite en local par défaut ; PostgreSQL dès que DATABASE_URL est définie.
# Le code métier n'utilise que l'ORM, compatible avec les deux moteurs.


def database_from_url(url):
    parsed = urlparse(url)
    if parsed.scheme in ("postgres", "postgresql"):
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": parsed.path.lstrip("/"),
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname or "",
            "PORT": str(parsed.port or ""),
            "CONN_MAX_AGE": 60,
        }
    if parsed.scheme == "sqlite":
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": parsed.path or "db.sqlite3"}
    raise RuntimeError(f"DATABASE_URL non reconnue : {url}")


_database_url = env("DATABASE_URL", "").strip()
DATABASES = {
    "default": database_from_url(_database_url)
    if _database_url
    else {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Authentification -------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:index"
LOGOUT_REDIRECT_URL = "accounts:login"

# Session : expiration glissante après 2 h d'inactivité, fin à la fermeture du navigateur.
SESSION_COOKIE_AGE = 2 * 60 * 60
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# Nom affiché dans l'application d'authentification (TOTP).
OTP_TOTP_ISSUER = "CEF Desk"

# Code d'invitation pour la création de comptes comité (vide => désactivé).
CEF_REGISTRATION_CODE = env("CEF_REGISTRATION_CODE", "").strip()

# --- HTTPS ------------------------------------------------------------------
# En production (DJANGO_FORCE_HTTPS=True) : redirection HTTPS, HSTS, cookies sécurisés.
FORCE_HTTPS = env_bool("DJANGO_FORCE_HTTPS", not DEBUG)
if FORCE_HTTPS:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# --- Internationalisation ---------------------------------------------------

LANGUAGE_CODE = "fr-ch"
TIME_ZONE = "Europe/Zurich"
USE_I18N = True
USE_TZ = True
USE_THOUSAND_SEPARATOR = True

# --- Fichiers statiques et médias -------------------------------------------

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Dossier des sauvegardes automatiques (commande `manage.py backup`).
BACKUP_DIR = Path(env("CEF_BACKUP_DIR", str(BASE_DIR / "backups")))
BACKUP_KEEP_DAYS = int(env("CEF_BACKUP_KEEP_DAYS", "30"))

# Taille max d'un fichier déposé dans l'espace de stockage (Mo).
DOCUMENTS_MAX_UPLOAD_MB = 25
DATA_UPLOAD_MAX_MEMORY_SIZE = DOCUMENTS_MAX_UPLOAD_MB * 1024 * 1024

# --- Email ------------------------------------------------------------------
# EMAIL_URL vide => backend console (développement). Exemple production :
#   smtp+tls://utilisateur:motdepasse@mail.infomaniak.com:587

_email_url = env("EMAIL_URL", "").strip()
if _email_url:
    _e = urlparse(_email_url)
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = _e.hostname or "localhost"
    EMAIL_PORT = _e.port or 587
    EMAIL_HOST_USER = unquote(_e.username or "")
    EMAIL_HOST_PASSWORD = unquote(_e.password or "")
    EMAIL_USE_TLS = _e.scheme == "smtp+tls"
    EMAIL_USE_SSL = _e.scheme == "smtp+ssl"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "CEF Desk <noreply@localhost>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# --- Interface --------------------------------------------------------------

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

MESSAGE_TAGS = {
    10: "secondary",  # debug
    20: "info",
    25: "success",
    30: "warning",
    40: "danger",
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
