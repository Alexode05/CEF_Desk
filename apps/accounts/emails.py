"""Envoi des emails de compte (vérification d'adresse) et aperçu des liens en développement local."""
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .security import email_verification_token

DEV_BACKENDS = {
    "django.core.mail.backends.console.EmailBackend",
    "django.core.mail.backends.locmem.EmailBackend",
}
DEV_LINK_SESSION_KEY = "cef_dev_email_link"


def dev_email_preview_enabled():
    """
    En développement local sans serveur email (DEBUG + backend console), les emails ne partent pas
    réellement : on affiche alors le lien directement à l'écran. Jamais en production.
    """
    return settings.DEBUG and settings.EMAIL_BACKEND in DEV_BACKENDS


def remember_dev_link(request, link):
    if dev_email_preview_enabled():
        request.session[DEV_LINK_SESSION_KEY] = link


def pop_dev_link(request):
    return request.session.pop(DEV_LINK_SESSION_KEY, None) if dev_email_preview_enabled() else None


def verification_link(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    return request.build_absolute_uri(reverse("accounts:verify_email", args=[uid, token]))


def send_verification_email(request, user):
    link = verification_link(request, user)
    days = max(1, settings.PASSWORD_RESET_TIMEOUT // 86400)
    body = render_to_string(
        "accounts/emails/verification.txt",
        {"user": user, "link": link, "days": days, "club_name": "Cercle d'Escrime de Founex"},
    )
    EmailMessage(subject="CEF Desk — vérifiez votre adresse email", body=body, to=[user.email]).send(fail_silently=False)
    remember_dev_link(request, link)
    return link
