"""
Middleware qui impose connexion + A2F vérifiée sur toute l'interface de gestion.

Seules les URL explicitement publiques (connexion, création de compte, écrans A2F,
formulaires publics d'inscription, fichiers statiques) sont accessibles sans être
connecté et vérifié par A2F — cf. cahier des charges section 11.
"""
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

from django_otp import user_has_device

PUBLIC_URL_NAMES = {
    "accounts:login",
    "accounts:register",
    "accounts:logout",
}

# Accessibles connecté mais pas encore vérifié A2F.
TWO_FACTOR_URL_NAMES = {
    "accounts:two_factor_setup",
    "accounts:two_factor_verify",
    "accounts:logout",
}

# Préfixes de chemin publics (formulaires publics, statiques, médias en dev).
PUBLIC_PATH_PREFIXES = (
    "/formulaires/public/",
    "/" + settings.STATIC_URL.lstrip("/"),
    "/" + settings.MEDIA_URL.lstrip("/"),
)


class LoginAndTwoFactorRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Appelé après la résolution d'URL : `request.resolver_match` est disponible ici."""
        path = request.path_info
        if path.startswith(PUBLIC_PATH_PREFIXES):
            return None

        match = request.resolver_match
        url_name = None
        if match is not None:
            url_name = f"{match.namespace}:{match.url_name}" if match.namespace else match.url_name

        # L'admin Django gère sa propre connexion ; on exige quand même l'A2F.
        is_admin = path.startswith("/admin/")

        user = request.user
        if not user.is_authenticated:
            if url_name in PUBLIC_URL_NAMES:
                return None
            if is_admin:
                return None  # l'admin affiche sa propre page de connexion
            return redirect(f"{reverse('accounts:login')}?next={request.get_full_path()}")

        # Connecté : l'A2F doit être configurée puis vérifiée pour cette session.
        if url_name in PUBLIC_URL_NAMES or url_name in TWO_FACTOR_URL_NAMES:
            return None

        if not user_has_device(user, confirmed=True):
            return redirect("accounts:two_factor_setup")

        if not user.is_verified():
            return redirect(f"{reverse('accounts:two_factor_verify')}?next={request.get_full_path()}")

        return None
