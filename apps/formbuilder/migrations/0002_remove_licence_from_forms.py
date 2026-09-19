"""Le numéro de licence n'est plus demandé dans les formulaires publics."""
from django.db import migrations


def forwards(apps, schema_editor):
    FormField = apps.get_model("formbuilder", "FormField")
    FormField.objects.filter(field_definition__key="licence_number").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("formbuilder", "0001_initial"),
        ("members", "0003_role_codes_and_field_layout"),
    ]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
