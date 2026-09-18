from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

User = get_user_model()


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Nom d'utilisateur", widget=forms.TextInput(attrs={"autofocus": True}))
    password = forms.CharField(label="Mot de passe", strip=False, widget=forms.PasswordInput)


class RegisterForm(UserCreationForm):
    """Création d'un compte comité, protégée par le code d'invitation du club."""

    first_name = forms.CharField(label="Prénom", max_length=150)
    last_name = forms.CharField(label="Nom", max_length=150)
    email = forms.EmailField(label="Adresse email")
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
        user.is_staff = True  # accès à l'admin Django (réservé au comité)
        if commit:
            user.save()
        return user


class TOTPTokenForm(forms.Form):
    token = forms.CharField(
        label="Code à 6 chiffres",
        min_length=6,
        max_length=6,
        widget=forms.TextInput(
            attrs={
                "autofocus": True,
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
                "pattern": "[0-9]*",
                "class": "form-control form-control-lg text-center",
            }
        ),
    )

    def clean_token(self):
        token = self.cleaned_data["token"].strip().replace(" ", "")
        if not token.isdigit():
            raise forms.ValidationError("Le code ne doit contenir que des chiffres.")
        return token
