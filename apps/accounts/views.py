import base64
from io import BytesIO

import qrcode
import qrcode.image.svg
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods
from django_otp import login as otp_login, user_has_device
from django_otp.plugins.otp_totp.models import TOTPDevice

from .forms import LoginForm, RegisterForm, TOTPTokenForm


class CefLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = False

    def get_success_url(self):
        # Après le mot de passe, on passe toujours par l'A2F (middleware).
        return super().get_success_url()

    def get_context_data(self, **kwargs):
        from django.conf import settings

        ctx = super().get_context_data(**kwargs)
        ctx["registration_enabled"] = bool(settings.CEF_REGISTRATION_CODE)
        return ctx


class CefLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")


@require_http_methods(["GET", "POST"])
def register(request):
    from django.conf import settings

    if request.user.is_authenticated:
        return redirect("dashboard:index")
    if not settings.CEF_REGISTRATION_CODE:
        messages.error(request, "La création de compte est désactivée sur cette installation.")
        return redirect("accounts:login")

    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(
            request,
            "Compte créé. Dernière étape obligatoire : configurez l'authentification à deux facteurs.",
        )
        return redirect("accounts:two_factor_setup")
    return render(request, "accounts/register.html", {"form": form})


def _safe_next(request, default="dashboard:index"):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return reverse_lazy(default)


def _qr_svg_data_uri(uri):
    img = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage, box_size=6, border=2)
    buf = BytesIO()
    img.save(buf)
    return "data:image/svg+xml;base64," + base64.b64encode(buf.getvalue()).decode()


@login_required
@require_http_methods(["GET", "POST"])
def two_factor_setup(request):
    """Configuration obligatoire de l'A2F (TOTP) — à la création du compte ou si aucun appareil confirmé."""
    user = request.user
    if user_has_device(user, confirmed=True):
        return redirect("accounts:two_factor_verify")

    # Un seul appareil non confirmé « en cours » par utilisateur.
    device = TOTPDevice.objects.filter(user=user, confirmed=False).first()
    if device is None:
        device = TOTPDevice.objects.create(user=user, name="Application d'authentification", confirmed=False)

    form = TOTPTokenForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if device.verify_token(form.cleaned_data["token"]):
            device.confirmed = True
            device.save(update_fields=["confirmed"])
            otp_login(request, device)
            messages.success(request, "Authentification à deux facteurs activée. Bienvenue dans CEF Desk !")
            return redirect("dashboard:index")
        form.add_error("token", "Code incorrect. Vérifiez l'heure de votre téléphone et réessayez.")

    # Secret en base32 pour la saisie manuelle.
    secret_b32 = base64.b32encode(device.bin_key).decode("utf-8").replace("=", "")
    return render(
        request,
        "accounts/two_factor_setup.html",
        {
            "form": form,
            "qr_data_uri": _qr_svg_data_uri(device.config_url),
            "secret": " ".join(secret_b32[i : i + 4] for i in range(0, len(secret_b32), 4)),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def two_factor_verify(request):
    user = request.user
    if not user_has_device(user, confirmed=True):
        return redirect("accounts:two_factor_setup")
    if user.is_verified():
        return redirect(_safe_next(request))

    form = TOTPTokenForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        token = form.cleaned_data["token"]
        for device in TOTPDevice.objects.filter(user=user, confirmed=True):
            if device.verify_token(token):
                otp_login(request, device)
                return redirect(_safe_next(request))
        form.add_error("token", "Code incorrect ou expiré.")
    return render(request, "accounts/two_factor_verify.html", {"form": form, "next": request.GET.get("next", "")})


@login_required
def profile(request):
    devices = TOTPDevice.objects.filter(user=request.user, confirmed=True)
    return render(request, "accounts/profile.html", {"devices": devices})
