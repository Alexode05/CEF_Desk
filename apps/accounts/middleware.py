"""
Middleware qui impose d'être connecté sur toute l'interface de gestion (y compris l'administration
technique et les fichiers téléversés).

Seules les URL explicitement publiques (connexion, création de compte, vérification d'email,
mot de passe oublié, formulaires publics d'inscription, fichiers statiques CSS/JS) sont
accessibles sans être connecté — cf. cahier des charges section 11.
"""
from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.urls import reverse

PUBLIC_URL_NAMES = {
    "accounts:login",
    "accounts:register",
    "accounts:logout",
    "accounts:verification_sent",
    "accounts:verify_email",
    "accounts:resend_verification",
    "accounts:password_reset",
    "accounts:password_reset_done",
    "accounts:password_reset_confirm",
    "accounts:password_reset_complete",
}

# Préfixes de chemin publics. Les fichiers téléversés (/media/ : factures, documents) n'en font
# PAS partie : ils ne sont accessibles qu'aux personnes connectées.
PUBLIC_PATH_PREFIXES = (
    "/formulaires/public/",
    "/" + settings.STATIC_URL.lstrip("/"),
)


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Appelé après la résolution d'URL : `request.resolver_match` est disponible ici."""
        if request.user.is_authenticated:
            return None
        if request.path_info.startswith(PUBLIC_PATH_PREFIXES):
            return None
        match = request.resolver_match
        url_name = None
        if match is not None:
            url_name = f"{match.namespace}:{match.url_name}" if match.namespace else match.url_name
        if url_name in PUBLIC_URL_NAMES:
            return None
        # Tout le reste (y compris /admin/) passe par la page de connexion de CEF Desk.
        return redirect_to_login(request.get_full_path(), reverse("accounts:login"))
