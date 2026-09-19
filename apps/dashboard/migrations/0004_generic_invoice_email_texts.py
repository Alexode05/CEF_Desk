"""Textes d'email valables pour les cotisations ET les factures manuelles.

Seuls les textes encore identiques aux anciens textes par défaut sont remplacés : un texte
personnalisé par le comité n'est jamais touché.
"""
from django.db import migrations

OLD_INVOICE_SUBJECT = "Cotisation {saison} — {prenom} {nom}"
OLD_INVOICE_BODY = (
    "Bonjour,\n\n"
    "Vous trouverez en pièce jointe la facture de cotisation pour la saison {saison} "
    "concernant {prenom} {nom} ({modalite}).\n\n"
    "Montant : CHF {montant}\n"
    "Échéance : {echeance}\n\n"
    "La facture comporte une QR-facture que vous pouvez scanner avec votre application bancaire.\n\n"
    "Avec nos salutations sportives,\n"
    "Le comité du Cercle d'Escrime de Founex"
)
OLD_REMINDER_SUBJECT = "Rappel — cotisation {saison} — {prenom} {nom}"
OLD_REMINDER_BODY = (
    "Bonjour,\n\n"
    "Sauf erreur de notre part, la facture n° {numero} (cotisation {saison}, {prenom} {nom}) "
    "d'un montant de CHF {montant}, échue le {echeance}, n'a pas encore été réglée.\n\n"
    "Vous la trouverez à nouveau en pièce jointe. Si le paiement a été effectué entre-temps, "
    "merci de ne pas tenir compte de ce rappel.\n\n"
    "Avec nos salutations sportives,\n"
    "Le comité du Cercle d'Escrime de Founex"
)

NEW_INVOICE_SUBJECT = "{titre} — {destinataire}"
NEW_INVOICE_BODY = (
    "Bonjour,\n\n"
    "Vous trouverez en pièce jointe la facture n° {numero} concernant {objet}.\n\n"
    "Montant : CHF {montant}\n"
    "Échéance : {echeance}\n\n"
    "La facture comporte une QR-facture que vous pouvez scanner avec votre application bancaire.\n\n"
    "Avec nos salutations sportives,\n"
    "Le comité du Cercle d'Escrime de Founex"
)
NEW_REMINDER_SUBJECT = "Rappel — {titre} — {destinataire}"
NEW_REMINDER_BODY = (
    "Bonjour,\n\n"
    "Sauf erreur de notre part, la facture n° {numero} ({objet}) d'un montant de CHF {montant}, "
    "échue le {echeance}, n'a pas encore été réglée.\n\n"
    "Vous la trouverez à nouveau en pièce jointe. Si le paiement a été effectué entre-temps, "
    "merci de ne pas tenir compte de ce rappel.\n\n"
    "Avec nos salutations sportives,\n"
    "Le comité du Cercle d'Escrime de Founex"
)


def forwards(apps, schema_editor):
    ClubSettings = apps.get_model("dashboard", "ClubSettings")
    for club in ClubSettings.objects.all():
        for field, old, new in (
            ("invoice_email_subject", OLD_INVOICE_SUBJECT, NEW_INVOICE_SUBJECT),
            ("invoice_email_body", OLD_INVOICE_BODY, NEW_INVOICE_BODY),
            ("reminder_email_subject", OLD_REMINDER_SUBJECT, NEW_REMINDER_SUBJECT),
            ("reminder_email_body", OLD_REMINDER_BODY, NEW_REMINDER_BODY),
        ):
            if getattr(club, field).replace("\r\n", "\n").strip() == old:  # un navigateur enregistre les retours en \r\n
                setattr(club, field, new)
        club.save()


class Migration(migrations.Migration):
    dependencies = [("dashboard", "0003_alter_clubsettings_invoice_email_body_and_more")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
