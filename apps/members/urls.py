from django.urls import path

from . import views

app_name = "members"

urlpatterns = [
    path("", views.member_list, name="list"),
    path("colonnes/", views.save_columns, name="save_columns"),
    path("vues/enregistrer/", views.save_view, name="save_view"),
    path("vues/<int:pk>/supprimer/", views.delete_view, name="delete_view"),
    path("nouveau/", views.member_create, name="create"),
    path("import/", views.member_import, name="import"),
    path("modification-de-masse/", views.mass_edit, name="mass_edit"),
    path("groupes/", views.group_manage, name="groups"),
    path("groupes/<int:pk>/modifier/", views.group_edit, name="group_edit"),
    path("groupes/<int:pk>/supprimer/", views.group_delete, name="group_delete"),
    path("champs/", views.field_manage, name="fields"),
    path("champs/<int:pk>/modifier/", views.field_edit, name="field_edit"),
    path("champs/<int:pk>/supprimer/", views.field_delete, name="field_delete"),
    path("champs/<int:pk>/sensible/", views.field_toggle_sensitive, name="field_toggle_sensitive"),
    path("<int:pk>/", views.member_detail, name="detail"),
    path("<int:pk>/modifier/", views.member_edit, name="edit"),
    path("<int:pk>/supprimer/", views.member_delete, name="delete"),
    path("<int:pk>/valider/", views.member_validate, name="validate"),
]
