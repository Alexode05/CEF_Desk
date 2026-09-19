from django.urls import path

from . import views

app_name = "mailing"

urlpatterns = [
    path("", views.index, name="index"),
    path("listes/nouvelle/", views.list_create, name="list_create"),
    path("listes/depuis-selection/", views.list_from_selection, name="list_from_selection"),
    path("listes/<int:pk>/", views.list_detail, name="list_detail"),
    path("listes/<int:pk>/membres/", views.list_set_members, name="list_set_members"),
    path("listes/<int:pk>/supprimer/", views.list_delete, name="list_delete"),
    path("envoyer/", views.campaign_compose, name="compose"),
]
