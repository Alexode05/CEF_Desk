from django.utils.http import url_has_allowed_host_and_scheme


def safe_next(request, default, param="next"):
    """Adresse de retour transmise par un formulaire, acceptée seulement si elle reste sur ce site."""
    target = request.POST.get(param) or request.GET.get(param)
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return target
    return default
