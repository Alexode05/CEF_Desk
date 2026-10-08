"""
Sécurité des comptes : jeton de vérification d'email et limitation des tentatives de connexion.

Depuis la décision d'Alex du 08.10.2026, la connexion se fait par mot de passe seul (plus d'A2F).
La limitation des tentatives compense en partie : après LOGIN_MAX_FAILURES échecs pour un même
identifiant depuis la même adresse IP (ou LOGIN_MAX_FAILURES_PER_IP depuis une même IP), la connexion
est bloquée pendant LOGIN_LOCKOUT_SECONDS.
"""
import hashlib

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.cache import cache


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """
    Jeton du lien de vérification envoyé à l'inscription.

    Il dépend de l'état « actif » du compte et de son adresse email : une fois le compte activé
    (ou l'adresse changée), le lien ne fonctionne plus. Durée de validité : PASSWORD_RESET_TIMEOUT.
    """

    key_salt = "apps.accounts.security.EmailVerificationTokenGenerator"

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{user.is_active}{user.email}{user.password}{timestamp}"


email_verification_token = EmailVerificationTokenGenerator()


# --- Limitation des tentatives de connexion -------------------------------------


def _client_ip(request):
    return (request.META.get("REMOTE_ADDR") or "inconnue") if request is not None else "inconnue"


def _keys(request, identifier):
    ip = _client_ip(request)
    ident = hashlib.sha256((identifier or "").strip().lower().encode()).hexdigest()[:24]
    return f"login-fail:{ip}:{ident}", f"login-fail-ip:{ip}"


def is_locked(request, identifier):
    pair_key, ip_key = _keys(request, identifier)
    return (cache.get(pair_key, 0) >= settings.LOGIN_MAX_FAILURES
            or cache.get(ip_key, 0) >= settings.LOGIN_MAX_FAILURES_PER_IP)


def register_failure(request, identifier):
    for key in _keys(request, identifier):
        cache.add(key, 0, timeout=settings.LOGIN_LOCKOUT_SECONDS)
        try:
            cache.incr(key)
        except ValueError:  # clé expirée entre add() et incr()
            cache.set(key, 1, timeout=settings.LOGIN_LOCKOUT_SECONDS)


def reset_failures(request, identifier):
    pair_key, _ = _keys(request, identifier)
    cache.delete(pair_key)


def lockout_minutes():
    return max(1, settings.LOGIN_LOCKOUT_SECONDS // 60)
