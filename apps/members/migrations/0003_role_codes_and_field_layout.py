"""Rôles en liste déroulante + libellés propres aux profils (données existantes)."""
import unicodedata

from django.db import migrations

ROLE_LABELS = {
    "TIREUR": "Tireur-euse", "COACH": "Coach", "MAITRE_ARMES": "Maître d'arme", "MEMBRE": "Membre",
    "COMITE": "Comité", "PRESIDENT": "Président-e", "VICE_PRESIDENT": "Vice-président-e",
    "TRESORIER": "Trésorier-ère", "SECRETAIRE": "Secrétaire", "VERIFICATEUR": "Vérificateur des comptes",
}


def _norm(value):
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    return "".join(c for c in value.lower() if c.isalnum())


def forwards(apps, schema_editor):
    Member = apps.get_model("members", "Member")
    FieldDefinition = apps.get_model("members", "FieldDefinition")

    lookup = {}
    for code, label in ROLE_LABELS.items():
        lookup[_norm(code)] = code
        lookup[_norm(label)] = code
    for member in Member.objects.exclude(role=""):
        code = lookup.get(_norm(member.role))
        if code:
            member.role = code
        else:  # ancien texte libre (ex. « Direction ») : conservé dans les remarques, rôle à choisir dans la liste
            note = f"Ancien rôle : {member.role}"
            member.notes = f"{member.notes}\n{note}".strip()
            member.role = ""
        member.save(update_fields=["role", "notes"])

    phone = FieldDefinition.objects.filter(key="phone", label="Téléphone élève").first()
    if phone:
        phone.label = "Téléphone escrimeur.euse"
        phone.save(update_fields=["label"])
    email = FieldDefinition.objects.filter(key="email").first()
    if email and not email.layout:
        email.layout = {"MINEUR": {"label": "Email élève"}}
        email.save(update_fields=["layout"])


class Migration(migrations.Migration):
    dependencies = [("members", "0002_fielddefinition_layout_fielddefinition_section_and_more")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
