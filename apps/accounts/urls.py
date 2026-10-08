from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = "accounts"

urlpatterns = [
    path("connexion/", views.CefLoginView.as_view(), name="login"),
    path("deconnexion/", views.CefLogoutView.as_view(), name="logout"),
    path("creer-un-compte/", views.register, name="register"),
    path("verification/envoyee/", views.verification_sent, name="verification_sent"),
    path("verification/renvoyer/", views.resend_verification, name="resend_verification"),
    path("verification/<uidb64>/<token>/", views.verify_email, name="verify_email"),
    path("mot-de-passe-oublie/", views.CefPasswordResetView.as_view(), name="password_reset"),
    path("mot-de-passe-oublie/envoye/", views.password_reset_done, name="password_reset_done"),
    path("mot-de-passe-oublie/<uidb64>/<token>/", views.CefPasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path(
        "mot-de-passe-oublie/termine/",
        auth_views.PasswordResetCompleteView.as_view(template_name="accounts/password_reset_complete.html"),
        name="password_reset_complete",
    ),
    path("profil/", views.profile, name="profile"),
    path(
        "mot-de-passe/",
        auth_views.PasswordChangeView.as_view(
            template_name="accounts/password_change.html", success_url=reverse_lazy("accounts:profile")
        ),
        name="password_change",
    ),
]
