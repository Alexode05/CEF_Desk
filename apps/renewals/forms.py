"""
Formulaires du passage de saison :
- RenewalForm : formulaire public personnel (données actuelles du membre, modifiables) ;
- LaunchForm : lancement par le comité (saison, texte de l'email) ;
- RenewalBillingForm : informations de facturation confirmées par le comité à la validation.
"""
from datetime import date
from decimal import Decimal

from django import forms
from django.db.models import Model, QuerySet

from apps.formbuilder.public_forms import _builtin_form_field
from apps.members import fields as F
from apps.members import services as member_services
from apps.members.forms import form_field_for_definition
from apps.members.models import (
    COUNTRY_LABELS,
    NATIONALITY_LABELS,
    WEEKDAY_LABELS,
    ContactGroup,
    FieldDefinition,
    TariffBracket,
    TrainingMode,
)

EMAIL_KEYS = {"email", "email_alt", "email_parent1", "email_parent2"}


# --- Valeurs : lecture sur la fiche, normalisation, affichage, application -------------------------


def editable_definitions(member):
    """Champs de la fiche que le membre peut vérifier : ceux de son profil, hors champs réservés au comité."""
    defs = [d for d in F.all_field_definitions(member.profile) if d.key not in F.NOT_IN_PUBLIC_FORMS]
    if not ContactGroup.objects.filter(public_choice=True).exists():
        defs = [d for d in defs if d.key != "groups"]
    return defs


def current_value(member, d):
    if not d.is_builtin:
        return (member.custom_data or {}).get(d.key)
    if d.key == "groups":
        return list(member.groups.filter(public_choice=True))  # seuls les groupes proposés au public sont modifiables
    if d.key == "training_days":
        return list(member.training_days or [])
    return getattr(member, d.key, None)


def normalize(value):
    """Forme comparable et enregistrable en JSON."""
    if value is None:
        return ""
    if isinstance(value, Model):
        return value.pk
    if isinstance(value, (list, tuple, QuerySet)):
        return sorted(normalize(v) for v in value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, str):
        return value.strip()
    return value


def display(d, value):
    """Valeur lisible (normalisée) pour le comité et l'email récapitulatif."""
    if value in ("", None, []):
        return "—"
    if isinstance(value, bool):
        return "Oui" if value else "Non"
    key = d.key
    if key == "groups":
        return ", ".join(ContactGroup.objects.filter(pk__in=value).order_by("sort_order", "name").values_list("name", flat=True))
    if key == "training_mode":
        mode = TrainingMode.objects.filter(pk=value).first()
        return str(mode) if mode else "—"
    if key == "country":
        return COUNTRY_LABELS.get(value, value)
    if key == "nationality":
        return NATIONALITY_LABELS.get(value, value)
    if d.field_type == "WEEKDAYS" or key == "training_days":
        return ", ".join(WEEKDAY_LABELS.get(v, v) for v in value)
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    if d.field_type == "DATE":
        try:
            return date.fromisoformat(str(value)).strftime("%d.%m.%Y")
        except ValueError:
            return str(value)
    bf = F.BUILTIN_BY_KEY.get(key)
    if bf and bf.choices:
        return dict(bf.choices).get(value, str(value))
    return str(value)


def apply_proposed(member, proposed):
    """Applique à la fiche les valeurs modifiées par le membre (et seulement celles-ci)."""
    defs = {d.key: d for d in FieldDefinition.objects.filter(key__in=list(proposed))}
    custom = dict(member.custom_data or {})
    new_public_groups = None
    for key, value in proposed.items():
        d = defs.get(key)
        if d is None:
            continue
        if not d.is_builtin:
            custom[key] = value if value != "" else None
        elif key == "groups":
            new_public_groups = value
        elif key == "training_mode":
            member.training_mode = TrainingMode.objects.filter(pk=value).first() if value else None
        elif key == "training_days":
            member.training_days = list(value or [])
        elif d.field_type == "DATE":
            setattr(member, key, date.fromisoformat(value) if value else None)
        elif d.field_type == "BOOLEAN":
            setattr(member, key, bool(value))
        elif key == "avs_number":
            member.avs_number = member_services.format_avs(value)
        else:
            setattr(member, key, value or "")
    member.custom_data = custom
    member.save()
    if new_public_groups is not None:
        kept = list(member.groups.filter(public_choice=False))  # Comité, Essais… : jamais modifiés par le membre
        chosen = list(ContactGroup.objects.filter(pk__in=new_public_groups, public_choice=True))
        member.groups.set(kept + chosen)


# --- Formulaire public ----------------------------------------------------------------------------


class RenewalForm(forms.Form):
    remark = forms.CharField(
        label="Remarque pour le comité (facultatif)", required=False, max_length=2000,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, member, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.member = member
        self.definitions = editable_definitions(member)
        fields = {}
        for d in self.definitions:
            label = d.label_for(member.profile)
            required = d.key in ("first_name", "last_name")
            if d.is_builtin:
                field = _builtin_form_field(d.key, label, required, d.help_text)
            else:
                field = form_field_for_definition(d, required=required)
                field.label = label
            if d.is_sensitive:
                # Donnée sensible (N° AVS…) : jamais affichée en clair sur une page publique.
                masked = member.avs_masked if d.key == "avs_number" else ("enregistré" if current_value(member, d) else "")
                field.required = False
                field.help_text = (f"Actuellement : {masked}. " if masked else "") + "Laissez vide pour ne rien changer."
            else:
                field.initial = current_value(member, d)
            fields[d.key] = field
        fields["remark"] = self.fields.pop("remark")
        self.fields = fields

    def clean_avs_number(self):
        value = (self.cleaned_data.get("avs_number") or "").strip()
        if value and not member_services.avs_is_valid(member_services.format_avs(value)):
            raise forms.ValidationError("Numéro AVS invalide (13 chiffres commençant par 756).")
        return member_services.format_avs(value) if value else ""

    def clean(self):
        cleaned = super().clean()
        email_fields = [d.key for d in self.definitions if d.key in EMAIL_KEYS]
        if email_fields and not any(cleaned.get(k) for k in email_fields):
            self.add_error(email_fields[0], "Merci d'indiquer au moins une adresse email de contact.")
        return cleaned

    def diff(self):
        """(valeurs modifiées à enregistrer, changements lisibles) — uniquement ce qui diffère de la fiche."""
        proposed, changes = {}, []
        for d in self.definitions:
            new = normalize(self.cleaned_data.get(d.key))
            if d.is_sensitive and new in ("", [], None):
                continue  # champ sensible laissé vide = inchangé
            old = normalize(current_value(self.member, d))
            if d.field_type == "BOOLEAN":  # case non cochée = « non », même si rien n'était enregistré
                old, new = bool(old), bool(new)
            if new == old or (old in ("", None, []) and new in ("", None, [])):
                continue
            proposed[d.key] = new
            changes.append({
                "key": d.key,
                "label": d.label_for(self.member.profile),
                "old": display(d, old),
                "new": display(d, new),
                "sensitive": d.is_sensitive,
            })
        return proposed, changes


# --- Comité ---------------------------------------------------------------------------------------


DEFAULT_SUBJECT = "Saison {saison} — vérification des données de {prenom} {nom}"
DEFAULT_BODY = (
    "Bonjour,\n\n"
    "La saison {saison} du Cercle d'Escrime de Founex se prépare. Pour mettre à jour nos fichiers et préparer "
    "la facturation, merci de vérifier les informations que nous avons sur {prenom} {nom} et de les corriger si "
    "nécessaire, en suivant ce lien personnel :\n\n"
    "{lien}\n\n"
    "Sur la même page, vous pouvez aussi nous annoncer la démission de {prenom} si l'escrime au club s'arrête.\n\n"
    "Ce lien est personnel et valable jusqu'au {date_limite}. Merci de ne pas le transférer.\n\n"
    "Avec nos salutations sportives,\n"
    "Le comité du Cercle d'Escrime de Founex"
)


class LaunchForm(forms.Form):
    target_season = forms.ChoiceField(label="Saison préparée")
    subject = forms.CharField(label="Sujet de l'email", max_length=200, initial=DEFAULT_SUBJECT)
    body = forms.CharField(
        label="Texte de l'email", widget=forms.Textarea(attrs={"rows": 14}), initial=DEFAULT_BODY,
        help_text="Variables : {prenom}, {nom}, {saison}, {lien} (obligatoire), {date_limite}.",
    )

    def __init__(self, *args, season_choices=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target_season"].choices = list(season_choices)

    def clean_body(self):
        body = self.cleaned_data["body"]
        if "{lien}" not in body:
            raise forms.ValidationError("Le texte doit contenir {lien} : c'est là que le lien personnel de chaque membre est inséré.")
        return body


class RenewalBillingForm(forms.Form):
    """À la validation, le comité confirme les informations de facturation de la nouvelle saison."""

    training_mode = forms.ModelChoiceField(label="Modalité d'entraînement", queryset=TrainingMode.objects.filter(is_active=True), required=False)
    tariff_bracket = forms.ModelChoiceField(label="Tranche tarifaire", queryset=TariffBracket.objects.all(), empty_label="— choisir —")
    family_discount = forms.BooleanField(label="Réduction famille (2ᵉ enfant et suivants) : -100 CHF", required=False)
