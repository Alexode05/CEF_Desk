"""Les profils d'un champ sont désormais toujours explicites (l'ancien « liste vide = tous » est converti)."""
from django.db import migrations


def forwards(apps, schema_editor):
    FieldDefinition = apps.get_model("members", "FieldDefinition")
    for d in FieldDefinition.objects.all():
        if not d.profiles:
            d.profiles = ["MINEUR", "MAJEUR", "ESSAI"]
            d.save(update_fields=["profiles"])


class Migration(migrations.Migration):
    dependencies = [("members", "0003_role_codes_and_field_layout")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
