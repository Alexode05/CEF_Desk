from .models import ClubSettings


def club_context(request):
    if not request.user.is_authenticated:
        return {}
    try:
        club = ClubSettings.load()
    except Exception:  # base non migrée
        return {}
    return {"club_settings": club, "current_season": club.current_season_label()}
