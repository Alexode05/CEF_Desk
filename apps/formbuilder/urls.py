from django.urls import path

from . import views

app_name = "formbuilder"

urlpatterns = [
    path("", views.form_list, name="list"),
    path("nouveau/", views.form_create, name="create"),
    path("<int:pk>/", views.form_edit, name="edit"),
    path("<int:pk>/supprimer/", views.form_delete, name="delete"),
    path("champ/<int:pk>/", views.field_edit, name="field_edit"),
    path("champ/<int:pk>/deplacer/<str:direction>/", views.field_move, name="field_move"),
    path("champ/<int:pk>/retirer/", views.field_delete, name="field_delete"),
    path("soumissions/", views.submission_list, name="submissions"),
    path("soumissions/<int:pk>/", views.submission_detail, name="submission_detail"),
    # Public (sans connexion) — préfixe protégé par le middleware : /formulaires/public/
    path("public/<slug:slug>/", views.public_form, name="public"),
]
