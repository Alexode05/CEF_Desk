from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.index, name="index"),
    path("notes/enregistrer/", views.save_note, name="save_note"),
    path("taches/ajouter/", views.todo_add, name="todo_add"),
    path("taches/<int:pk>/basculer/", views.todo_toggle, name="todo_toggle"),
    path("taches/<int:pk>/modifier/", views.todo_edit, name="todo_edit"),
    path("taches/<int:pk>/supprimer/", views.todo_delete, name="todo_delete"),
    path("parametres/", views.club_settings, name="settings"),
]
