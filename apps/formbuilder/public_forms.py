"""
Construction dynamique du formulaire public Django à partir d'une `FormDefinition`,
validation côté serveur (y compris les règles conditionnelles) et création de la fiche membre.
"""
import time

from django import forms
from django.core import signing

from apps.members import fields as F
from apps.members import services as member_services
from apps.members.forms import DATE_INPUT, form_field_for_definition
from django.db.models import QuerySet

from apps.members.models import WEEKDAYS, ContactGroup, Member, MemberStatus, Profile, TariffBracket, TrainingMode

from .models import FormField

HONEYPOT_NAME = "website_url"
MIN_SECONDS = 3  # un humain ne remplit pas un formulaire d'inscription en moins de 3 s


def _builtin_form_field(key, label, required, help_text):
    """Champ Django pour un champ natif de la fiche (types/choix cohérents avec le modèle)."""
    bf = F.BUILTIN_BY_KEY[key]
    common = {"label": label, "required": required, "help_text": help_text}
    t = bf.field_type
    if key == "groups":  # créneau(x) de cours proposés à l'inscription
        return forms.ModelMultipleChoiceField(
            queryset=ContactGroup.objects.filter(public_choice=True), widget=forms.CheckboxSelectMultiple, **common
        )
    if key == "training_mode":
        return forms.ModelChoiceField(queryset=TrainingMode.objects.filter(is_active=True), empty_label="—", **common)
    if key == "tariff_bracket":
        return forms.ModelChoiceField(queryset=TariffBracket.objects.all(), empty_label="—", **common)
    if t == "SELECT":
        return forms.ChoiceField(choices=[("", "—")] + list(bf.choices), **common)
    if t == "WEEKDAYS":
        return forms.MultipleChoiceField(choices=WEEKDAYS, widget=forms.CheckboxSelectMultiple, **common)
    if t == "MULTISELECT":
        return forms.MultipleChoiceField(choices=list(bf.choices), widget=forms.CheckboxSelectMultiple, **common)
    if t == "DATE":
        return forms.DateField(widget=DATE_INPUT, **common)
    if t == "EMAIL":
        return forms.EmailField(**common)
    if t == "PHONE":
        return forms.CharField(max_length=30, widget=forms.TextInput(attrs={"type": "tel"}), **common)
    if t == "TEXTAREA":
        return forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), **common)
    if t == "BOOLEAN":
        return forms.BooleanField(**{**common, "required": False})
    max_length = Member._meta.get_field(key).max_length if key in {f.name for f in Member._meta.fields} else 200
    return forms.CharField(max_length=max_length or 200, **common)


class PublicForm(forms.Form):
    """Formulaire public généré. Les champs conditionnels masqués ne sont ni requis ni conservés."""

    def __init__(self, definition, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.definition = definition
        self.form_fields = list(definition.fields.select_related("field_definition", "condition_field"))
        self.field_map = {}
        for ff in self.form_fields:
            if not ff.is_input:
                continue
            if ff.kind == FormField.Kind.PROFILE:
                fld = forms.ChoiceField(
                    label=ff.effective_label, required=True, help_text=ff.help_text,
                    choices=[(Profile.MINEUR, "Mineur (moins de 18 ans)"), (Profile.MAJEUR, "Majeur")],
                    widget=forms.RadioSelect,
                )
            else:
                d = ff.field_definition
                if d is None or not d.is_active:
                    continue
                if d.key == "groups" and not ContactGroup.objects.filter(public_choice=True).exists():
                    continue  # aucun groupe proposé au public : le champ n'a pas lieu d'être
                if d.is_builtin:
                    fld = _builtin_form_field(d.key, ff.effective_label, ff.required, ff.help_text)
                else:
                    fld = form_field_for_definition(d, required=ff.required)
                    fld.label = ff.effective_label
                    fld.help_text = ff.help_text
            self.fields[ff.input_name] = fld
            self.field_map[ff.input_name] = ff

        # Anti-spam : honeypot (doit rester vide) + horodatage signé (délai minimal).
        self.fields[HONEYPOT_NAME] = forms.CharField(required=False, widget=forms.TextInput(attrs={"autocomplete": "off", "tabindex": "-1"}))
        self.fields["ts_token"] = forms.CharField(required=False, widget=forms.HiddenInput)
        if not self.is_bound:
            self.fields["ts_token"].initial = signing.dumps(int(time.time()))

    def raw_values(self):
        """Valeurs brutes soumises (pour évaluer les conditions avant validation complète)."""
        out = {}
        for name, ff in self.field_map.items():
            fld = self.fields[name]
            if isinstance(fld, forms.MultipleChoiceField):
                out[name] = self.data.getlist(name) if hasattr(self.data, "getlist") else self.data.get(name, [])
            else:
                out[name] = self.data.get(name, "")
        return out

    def visible_names(self):
        values = self.raw_values()
        return {name for name, ff in self.field_map.items() if ff.condition_met(values)}

    def clean(self):
        cleaned = super().clean()
        if cleaned.get(HONEYPOT_NAME):
            raise forms.ValidationError("Soumission refusée.")
        try:
            ts = signing.loads(cleaned.get("ts_token") or "", max_age=60 * 60 * 6)
            if time.time() - ts < MIN_SECONDS:
                raise forms.ValidationError("Soumission trop rapide, merci de réessayer.")
        except signing.BadSignature:
            raise forms.ValidationError("Formulaire expiré, merci de recharger la page.")

        # Champs masqués par une condition : on ignore leur valeur et leurs erreurs « requis ».
        visible = self.visible_names()
        for name, ff in self.field_map.items():
            if name not in visible:
                cleaned.pop(name, None)
                self.errors.pop(name, None)

        # Règle métier : au moins une adresse email (élève, parent ou alternative) pour pouvoir
        # envoyer la confirmation et les factures — si le formulaire comporte un champ email.
        email_keys = {"email", "email_parent1", "email_parent2", "email_alt"}
        email_names = [n for n, ff in self.field_map.items() if ff.field_definition and ff.field_definition.key in email_keys and n in visible]
        if email_names and not any(cleaned.get(n) for n in email_names):
            self.add_error(email_names[0], "Merci d'indiquer au moins une adresse email de contact.")
        return cleaned

    # --- Exploitation ---
    def resolved_profile(self):
        for name, ff in self.field_map.items():
            if ff.kind == FormField.Kind.PROFILE and self.cleaned_data.get(name):
                return self.cleaned_data[name]
        return self.definition.profile

    def answers(self):
        """Liste ordonnée {label, key, value} de toutes les réponses visibles (pour l'email et l'archive)."""
        out = []
        for ff in self.form_fields:
            name = ff.input_name
            if name not in self.cleaned_data:
                continue
            value = self.cleaned_data[name]
            key = ff.field_definition.key if ff.field_definition else ("__profile" if ff.kind == FormField.Kind.PROFILE else None)
            out.append({"label": ff.effective_label, "key": key, "value": _display(value, ff)})
        return out

    def build_member(self, created_by=None):
        profile = self.resolved_profile()
        member = Member(profile=profile, status=MemberStatus.EN_ATTENTE, created_by=created_by)
        self.selected_groups = []  # relation M2M : appliquée après l'enregistrement de la fiche
        custom = {}
        for name, ff in self.field_map.items():
            if name not in self.cleaned_data or ff.field_definition is None:
                continue
            d = ff.field_definition
            value = self.cleaned_data[name]
            if d.is_builtin:
                if d.key in F.NOT_IN_PUBLIC_FORMS or F.BUILTIN_BY_KEY[d.key].computed:
                    continue
                if d.key == "groups":
                    self.selected_groups = list(value or [])
                    continue
                if d.key == "avs_number":
                    value = member_services.format_avs(value)
                if d.key in ("training_mode", "tariff_bracket"):
                    setattr(member, d.key, value)
                else:
                    setattr(member, d.key, value if value is not None else "")
            else:
                if hasattr(value, "isoformat"):
                    value = value.isoformat()
                elif value is not None and d.field_type == "NUMBER":
                    value = str(value)
                custom[d.key] = value
        member.custom_data = custom
        return member


def _display(value, ff):
    if value is None or value == "":
        return ""
    if isinstance(value, QuerySet):
        return ", ".join(str(v) for v in value)
    if isinstance(value, (list, tuple)):
        from apps.members.models import WEEKDAY_LABELS

        return ", ".join(WEEKDAY_LABELS.get(v, str(v)) for v in value)
    if hasattr(value, "strftime"):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, bool):
        return "Oui" if value else "Non"
    if ff.kind == FormField.Kind.PROFILE:
        return dict(Profile.choices).get(value, value)
    d = ff.field_definition
    if d and d.is_builtin:
        bf = F.BUILTIN_BY_KEY.get(d.key)
        if bf and bf.choices:
            return dict(bf.choices).get(value, str(value))
    return str(value)
