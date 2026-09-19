"""Formulaires existants : plus de titre (civilité), ajout du choix du groupe."""
from django.db import migrations
from django.db.models import Max


def forwards(apps, schema_editor):
    FormField = apps.get_model("formbuilder", "FormField")
    FormDefinition = apps.get_model("formbuilder", "FormDefinition")
    FieldDefinition = apps.get_model("members", "FieldDefinition")

    FormField.objects.filter(field_definition__key="title").delete()

    groups = FieldDefinition.objects.filter(key="groups").first()
    if groups is None:
        return
    for form in FormDefinition.objects.all():
        if FormField.objects.filter(form=form, field_definition=groups).exists():
            continue
        anchor = FormField.objects.filter(form=form, field_definition__key="training_days").first()
        order = anchor.order + 1 if anchor else (FormField.objects.filter(form=form).aggregate(m=Max("order"))["m"] or 0) + 10
        FormField.objects.create(form=form, order=order, kind="FIELD", field_definition=groups, required=False)


class Migration(migrations.Migration):
    dependencies = [
        ("formbuilder", "0002_remove_licence_from_forms"),
        ("members", "0006_group_public_choice"),
    ]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
