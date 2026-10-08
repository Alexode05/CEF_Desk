from django.urls import path

from . import views

app_name = "renewals"

urlpatterns = [
    path("", views.launch, name="launch"),
    path("<int:pk>/", views.rollover_detail, name="rollover"),
    path("reponse/<int:pk>/", views.review, name="review"),
    path("invitation/<int:pk>/renvoyer/", views.resend, name="resend"),
    # Public (sans connexion) : lien personnel envoyé par email — autorisé par le middleware (nom d'URL).
    path("verifier/<str:token>/", views.public_form, name="public_form"),
]
