"""Crée les deux listes de diffusion automatiques « à facturer » (demande d'Alex du 08.10.2026)."""
from django.db import migrations

LISTS = [
    (
        "MEMBERSHIP",
        "Inscriptions définitives à facturer",
        "Automatique : inscriptions validées (Actif) dont la facture de cotisation de la saison n'est pas encore envoyée.",
    ),
    (
        "TRIAL",
        "Cours d'essai à facturer",
        "Automatique : cours d'essai validés dont la facture d'essai n'est pas encore envoyée.",
    ),
]


def forwards(apps, schema_editor):
    MailingList = apps.get_model("mailing", "MailingList")
    for rule, name, description in LISTS:
        if MailingList.objects.filter(kind="BILLING", billing_rule=rule).exists():
            continue
        if MailingList.objects.filter(name__iexact=name).exists():
            name = f"{name} (automatique)"
        MailingList.objects.create(name=name, kind="BILLING", billing_rule=rule, description=description)


def backwards(apps, schema_editor):
    apps.get_model("mailing", "MailingList").objects.filter(kind="BILLING").delete()


class Migration(migrations.Migration):
    dependencies = [("mailing", "0002_mailinglist_billing_rule_alter_mailinglist_kind")]
    operations = [migrations.RunPython(forwards, backwards)]
