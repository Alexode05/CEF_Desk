from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("connexion/", views.CefLoginView.as_view(), name="login"),
    path("deconnexion/", views.CefLogoutView.as_view(), name="logout"),
    path("creer-un-compte/", views.register, name="register"),
    path("a2f/configuration/", views.two_factor_setup, name="two_factor_setup"),
    path("a2f/verification/", views.two_factor_verify, name="two_factor_verify"),
    path("profil/", views.profile, name="profile"),
    path(
        "mot-de-passe/",
        auth_views.PasswordChangeView.as_view(
            template_name="accounts/password_change.html", success_url="/compte/profil/"
        ),
        name="password_change",
    ),
]
