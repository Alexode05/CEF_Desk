from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    path("", views.index, name="index"),
    path("dossier/nouveau/", views.create_folder, name="create_root_folder"),
    path("dossier/<int:parent_pk>/nouveau/", views.create_folder, name="create_folder"),
    path("dossier/<int:folder_pk>/deposer/", views.upload, name="upload"),
    path("fichier/<int:pk>/telecharger/", views.download, name="download"),
    path("<str:kind>/<int:pk>/renommer/", views.rename, name="rename"),
    path("<str:kind>/<int:pk>/supprimer/", views.delete, name="delete"),
]
