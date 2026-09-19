"""Groupes proposés à l'inscription + libellé « Statut de la facture »."""
from django.db import migrations, models


def forwards(apps, schema_editor):
    ContactGroup = apps.get_model("members", "ContactGroup")
    FieldDefinition = apps.get_model("members", "FieldDefinition")
    ContactGroup.objects.filter(is_course=True).update(public_choice=True)  # les créneaux de cours sont choisis par l'inscrit
    FieldDefinition.objects.filter(key="invoice_status_label", label="Dernière facture").update(label="Statut de la facture")


class Migration(migrations.Migration):
    dependencies = [("members", "0005_multiple_roles")]
    operations = [
        migrations.AddField(
            model_name="contactgroup",
            name="public_choice",
            field=models.BooleanField(
                default=False,
                help_text="La personne qui s'inscrit peut choisir ce groupe (ex. son créneau de cours).",
                verbose_name="Proposé dans les formulaires d'inscription",
            ),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
