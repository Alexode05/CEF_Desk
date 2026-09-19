import os

from django.conf import settings

from .models import ClubSettings

_ASSETS = ("css/cefdesk.css", "js/cefdesk.js")


def _asset_version():
    """Date de dernière modification des fichiers CSS/JS : change à chaque mise à jour, ce qui évite les anciennes versions en cache."""
    latest = 0
    for rel in _ASSETS:
        try:
            latest = max(latest, int(os.path.getmtime(os.path.join(settings.BASE_DIR, "static", *rel.split("/")))))
        except OSError:
            pass
    return str(latest)  # texte : évite le formatage avec séparateurs de milliers


def club_context(request):
    context = {"asset_version": _asset_version()}
    if not request.user.is_authenticated:
        return context
    try:
        club = ClubSettings.load()
    except Exception:  # base non migrée
        return context
    context.update({"club_settings": club, "current_season": club.current_season_label()})
    return context
