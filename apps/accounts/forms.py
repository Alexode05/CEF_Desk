from django import forms
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, UserCreationForm

from . import security
from .emails import remember_dev_link
from .models import AccountProfile

User = get_user_model()


class LoginForm(AuthenticationForm):
    """
    Connexion par mot de passe (nom d'utilisateur OU adresse email).

    - compte non vérifié : message dédié + lien pour renvoyer l'email de vérification ;
    - trop d'échecs : blocage temporaire (cf. apps.accounts.security).
    """

    username = forms.CharField(
        label="Nom d'utilisateur ou adresse email",
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}),
    )
    password = forms.CharField(
        label="Mot de passe", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "current-password"})
    )

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Identifiant ou mot de passe incorrect.",
        "inactive": "Ce compte est désactivé. Contactez un membre du comité.",
        "unverified": "Votre adresse email n'est pas encore vérifiée : cliquez sur le lien reçu par email lors de l'inscription.",
        "locked": "Trop de tentatives de connexion. Réessayez dans %(minutes)s minutes ou utilisez « Mot de passe oublié ».",
    }

    def clean(self):
        identifier = (self.cleaned_data.get("username") or "").strip()
        password = self.cleaned_data.get("password")
        if not identifier or not password:
            return self.cleaned_data

        username = identifier
        if "@" in identifier:
            match = User.objects.filter(email__iexact=identifier).order_by("pk").first()
            if match:
                username = match.username
        self.cleaned_data["username"] = username

        if security.is_locked(self.request, username):
            raise forms.ValidationError(self.error_messages["locked"], code="locked", params={"minutes": security.lockout_minutes()})

        self.user_cache = authenticate(self.request, username=username, password=password)
        if self.user_cache is None:
            candidate = User.objects.filter(username=username).first()
            if candidate is not None and not candidate.is_active and candidate.check_password(password):
                profile = AccountProfile.for_user(candidate)
                code = "inactive" if profile.email_verified else "unverified"
                raise forms.ValidationError(self.error_messages[code], code=code)
            security.register_failure(self.request, username)
            raise self.get_invalid_login_error()

        self.confirm_login_allowed(self.user_cache)
        security.reset_failures(self.request, username)
        return self.cleaned_data


class RegisterForm(UserCreationForm):
    """
    Création d'un compte comité, protégée par le code d'invitation du club. Le compte reste
    inactif tant que l'adresse email n'a pas été vérifiée par le lien envoyé.
    """

    first_name = forms.CharField(label="Prénom", max_length=150)
    last_name = forms.CharField(label="Nom", max_length=150)
    email = forms.EmailField(label="Adresse email", help_text="Un lien de vérification y sera envoyé.")
    invitation_code = forms.CharField(
        label="Code d'invitation du comité",
        help_text="Code communiqué par le comité pour autoriser la création d'un compte.",
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email")
        labels = {"username": "Nom d'utilisateur"}

    def clean_invitation_code(self):
        code = self.cleaned_data["invitation_code"].strip()
        expected = settings.CEF_REGISTRATION_CODE
        if not expected:
            raise forms.ValidationError("La création de compte est désactivée (aucun code d'invitation configuré).")
        if code != expected:
            raise forms.ValidationError("Code d'invitation incorrect.")
        return code

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Un compte existe déjà avec cette adresse email.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_active = False  # activé par le lien de vérification
        user.is_staff = True  # accès à l'administration technique (réservé au comité)
        if commit:
            user.save()
            AccountProfile.for_user(user)
        return user


class ResendVerificationForm(forms.Form):
    email = forms.EmailField(label="Adresse email utilisée à l'inscription")


class CefPasswordResetForm(PasswordResetForm):
    """Réinitialisation du mot de passe par email (comptes actifs uniquement)."""

    email = forms.EmailField(label="Adresse email du compte", max_length=254, widget=forms.EmailInput(attrs={"autocomplete": "email"}))

    def send_mail(self, subject_template_name, email_template_name, context, from_email, to_email, html_email_template_name=None):
        super().send_mail(subject_template_name, email_template_name, context, from_email, to_email, html_email_template_name)
        request = getattr(self, "_request", None)
        if request is not None:
            from django.urls import reverse

            path = reverse("accounts:password_reset_confirm", args=[context["uid"], context["token"]])
            remember_dev_link(request, f"{context['protocol']}://{context['domain']}{path}")
