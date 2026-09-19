"""Un contact peut cumuler plusieurs rôles : `role` (texte) devient `roles` (liste)."""
from django.db import migrations, models


def forwards(apps, schema_editor):
    Member = apps.get_model("members", "Member")
    FieldDefinition = apps.get_model("members", "FieldDefinition")
    UserListPreference = apps.get_model("members", "UserListPreference")
    SavedView = apps.get_model("members", "SavedView")

    for member in Member.objects.exclude(role=""):
        member.roles = [member.role]
        member.save(update_fields=["roles"])

    definition = FieldDefinition.objects.filter(key="role").first()
    if definition and not FieldDefinition.objects.filter(key="roles").exists():
        definition.key = "roles"
        definition.field_type = "MULTISELECT"
        if definition.label == "Rôle":
            definition.label = "Rôles"
        definition.save()

    def rename(cols):
        return ["roles" if c == "role" else c for c in (cols or [])]

    for pref in UserListPreference.objects.all():
        pref.columns = rename(pref.columns)
        pref.save(update_fields=["columns"])
    for view in SavedView.objects.all():
        view.columns = rename(view.columns)
        view.filters = [dict(f, key="roles") if f.get("key") == "role" else f for f in (view.filters or [])]
        view.save(update_fields=["columns", "filters"])


class Migration(migrations.Migration):
    dependencies = [("members", "0004_profiles_explicit")]
    operations = [
        migrations.AddField(
            model_name="member",
            name="roles",
            field=models.JSONField(blank=True, default=list, help_text="Une personne peut cumuler plusieurs rôles.", verbose_name="Rôles"),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
        migrations.RemoveField(model_name="member", name="role"),
    ]
