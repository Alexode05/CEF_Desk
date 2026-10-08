"""
Comptes du comité : inscription avec vérification de l'adresse email, connexion par mot de passe,
mot de passe oublié. (L'A2F par application externe a été retirée le 08.10.2026 à la demande d'Alex.)
"""
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.http import require_http_methods

from .emails import pop_dev_link, send_verification_email
from .forms import CefPasswordResetForm, LoginForm, RegisterForm, ResendVerificationForm
from .models import AccountProfile
from .security import email_verification_token

logger = logging.getLogger(__name__)
User = get_user_model()

VERIFY_EMAIL_SESSION_KEY = "cef_pending_verification_email"


class CefLoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["registration_enabled"] = bool(settings.CEF_REGISTRATION_CODE)
        form = ctx.get("form")
        ctx["show_resend_link"] = bool(form is not None and form.is_bound and form.has_error("__all__", code="unverified"))
        return ctx


class CefLogoutView(auth_views.LogoutView):
    next_page = reverse_lazy("accounts:login")


def _send_or_report(request, user):
    try:
        send_verification_email(request, user)
        return True
    except Exception:  # noqa: BLE001 — serveur email indisponible : le compte reste créé, renvoi possible
        logger.exception("Envoi de l'email de vérification impossible")
        messages.error(request, "L'email de vérification n'a pas pu être envoyé. Réessayez dans quelques minutes avec « Renvoyer l'email ».")
        return False


@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard:index")
    if not settings.CEF_REGISTRATION_CODE:
        messages.error(request, "La création de compte est désactivée sur cette installation.")
        return redirect("accounts:login")

    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        _send_or_report(request, user)
        request.session[VERIFY_EMAIL_SESSION_KEY] = user.email
        return redirect("accounts:verification_sent")
    return render(request, "accounts/register.html", {"form": form})


def verification_sent(request):
    return render(
        request,
        "accounts/verification_sent.html",
        {"email": request.session.get(VERIFY_EMAIL_SESSION_KEY), "dev_link": pop_dev_link(request)},
    )


def verify_email(request, uidb64, token):
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and user.is_active and AccountProfile.for_user(user).email_verified:
        messages.info(request, "Cette adresse email est déjà vérifiée : vous pouvez vous connecter.")
        return redirect("accounts:login")

    if user is None or not email_verification_token.check_token(user, token):
        return render(request, "accounts/verification_failed.html", status=400)

    user.is_active = True
    user.save(update_fields=["is_active"])
    AccountProfile.for_user(user).mark_verified()
    request.session.pop(VERIFY_EMAIL_SESSION_KEY, None)
    messages.success(request, "Adresse email vérifiée, votre compte est activé. Connectez-vous avec votre mot de passe.")
    return redirect("accounts:login")


@require_http_methods(["GET", "POST"])
def resend_verification(request):
    form = ResendVerificationForm(request.POST or None, initial={"email": request.session.get(VERIFY_EMAIL_SESSION_KEY, "")})
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        user = User.objects.filter(email__iexact=email, is_active=False).first()
        if user is not None and not AccountProfile.for_user(user).email_verified:
            _send_or_report(request, user)
        # Même réponse dans tous les cas : on ne révèle pas quelles adresses ont un compte.
        request.session[VERIFY_EMAIL_SESSION_KEY] = email
        return redirect("accounts:verification_sent")
    return render(request, "accounts/resend_verification.html", {"form": form})


class CefPasswordResetView(auth_views.PasswordResetView):
    form_class = CefPasswordResetForm
    template_name = "accounts/password_reset_form.html"
    email_template_name = "accounts/emails/password_reset.txt"
    subject_template_name = "accounts/emails/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")

    def form_valid(self, form):
        form._request = self.request  # pour l'aperçu du lien en développement local
        return super().form_valid(form)


def password_reset_done(request):
    return render(request, "accounts/password_reset_done.html", {"dev_link": pop_dev_link(request)})


class CefPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")


@login_required
def profile(request):
    return render(request, "accounts/profile.html", {"account_profile": AccountProfile.for_user(request.user)})
