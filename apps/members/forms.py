from django import forms
from django.core.exceptions import ValidationError

from . import fields as F
from . import services
from .models import (
    WEEKDAYS,
    ContactGroup,
    ContactKind,
    FieldDefinition,
    FieldType,
    Member,
    MemberStatus,
    Profile,
    TariffBracket,
    TrainingMode,
)

DATE_INPUT = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


def form_field_for_definition(d: FieldDefinition, required=False):
    """Construit un champ de formulaire Django à partir d'une `FieldDefinition` personnalisée."""
    common = {"label": d.label, "required": required, "help_text": d.help_text}
    t = d.field_type
    if t == FieldType.TEXTAREA:
        return forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), **common)
    if t == FieldType.EMAIL:
        return forms.EmailField(**common)
    if t == FieldType.PHONE:
        return forms.CharField(max_length=30, widget=forms.TextInput(attrs={"type": "tel"}), **common)
    if t == FieldType.DATE:
        return forms.DateField(widget=DATE_INPUT, **common)
    if t == FieldType.SELECT:
        return forms.ChoiceField(choices=[("", "—")] + d.choice_pairs, **common)
    if t == FieldType.MULTISELECT:
        return forms.MultipleChoiceField(choices=d.choice_pairs, widget=forms.CheckboxSelectMultiple, **common)
    if t == FieldType.WEEKDAYS:
        return forms.MultipleChoiceField(choices=WEEKDAYS, widget=forms.CheckboxSelectMultiple, **common)
    if t == FieldType.BOOLEAN:
        return forms.BooleanField(**{**common, "required": False})
    if t == FieldType.NUMBER:
        return forms.DecimalField(max_digits=12, decimal_places=2, **common)
    return forms.CharField(max_length=200, **common)


class MemberForm(forms.ModelForm):
    """
    Formulaire de fiche membre : le jeu de champs dépend du profil (Mineur / Majeur / Essai).
    Les champs personnalisés actifs sont ajoutés dynamiquement (préfixe `custom__`).
    """

    training_days = forms.MultipleChoiceField(
        label="Jours d'entraînement", choices=WEEKDAYS, widget=forms.CheckboxSelectMultiple, required=False
    )

    class Meta:
        model = Member
        fields = [
            "kind", "company_name", "title", "first_name", "last_name", "address", "postal_code", "city",
            "country", "sex", "birth_date", "nationality", "entry_date", "exit_date", "status", "role",
            "groups", "avs_number", "laterality", "licence_number", "phone", "phone_parent1", "phone_parent2",
            "email", "email_alt", "email_parent1", "email_parent2", "training_mode", "training_days",
            "tariff_bracket", "family_discount", "notes",
        ]
        widgets = {
            "birth_date": DATE_INPUT,
            "entry_date": DATE_INPUT,
            "exit_date": DATE_INPUT,
            "groups": forms.CheckboxSelectMultiple,
            "notes": forms.Textarea(attrs={"rows": 3}),
            "avs_number": forms.TextInput(attrs={"placeholder": "756.XXXX.XXXX.XX", "autocomplete": "off"}),
            "phone": forms.TextInput(attrs={"type": "tel"}),
            "phone_parent1": forms.TextInput(attrs={"type": "tel"}),
            "phone_parent2": forms.TextInput(attrs={"type": "tel"}),
        }

    def __init__(self, *args, profile, **kwargs):
        super().__init__(*args, **kwargs)
        self.profile = profile
        # Le modèle de fiche (champs affichés, libellés, ordre, sections) vient de la base : il est
        # modifiable par le comité depuis « Modèle des fiches ».
        self.defs = {d.key: d for d in F.all_field_definitions(profile)}
        self.custom_definitions = [d for d in self.defs.values() if not d.is_builtin]

        # Champs natifs applicables au profil (+ champs de gestion toujours présents).
        applicable = {
            k for k, d in self.defs.items() if d.is_builtin and k in F.BUILTIN_BY_KEY and not F.BUILTIN_BY_KEY[k].computed
        }
        applicable |= {"kind", "company_name"} | F.LOCKED_FIELDS
        for key in list(self.fields):
            if key not in applicable:
                del self.fields[key]

        # Libellés propres au profil.
        for key, ff in self.fields.items():
            d = self.defs.get(key)
            if d:
                ff.label = d.label_for(profile)

        if profile == Profile.ESSAI:
            # Statut figé sur « Essai » (ou « En attente ») : non modifiable à la main.
            self.fields["status"].choices = [
                (MemberStatus.ESSAI, "Essai"),
                (MemberStatus.EN_ATTENTE, "En attente de validation"),
                (MemberStatus.INACTIF, "Inactif / sorti"),
            ]
            if not self.instance.pk:
                self.initial["status"] = MemberStatus.ESSAI
        else:
            self.fields["status"].choices = [c for c in MemberStatus.choices if c[0] != MemberStatus.ESSAI]
            if self.instance.pk and self.instance.status == MemberStatus.ESSAI:
                self.fields["status"].choices = list(MemberStatus.choices)
            if not self.instance.pk:
                # Création manuelle par le comité : fiche directement active (les soumissions
                # de formulaire, elles, arrivent toujours « en attente de validation »).
                self.initial["status"] = MemberStatus.ACTIF

        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        if "training_mode" in self.fields:
            self.fields["training_mode"].queryset = TrainingMode.objects.filter(is_active=True)
        if "groups" in self.fields:
            self.fields["groups"].queryset = ContactGroup.objects.all()
        if "tariff_bracket" in self.fields:
            self.fields["tariff_bracket"].queryset = TariffBracket.objects.all()
        if "training_days" in self.fields and self.instance.pk:
            self.initial["training_days"] = self.instance.training_days

        # Champs personnalisés.
        existing = self.instance.custom_data or {}
        for d in self.custom_definitions:
            name = f"custom__{d.key}"
            self.fields[name] = form_field_for_definition(d)
            self.fields[name].label = d.label_for(profile)
            if d.key in existing:
                self.initial[name] = existing[d.key]

        # Ordre propre au profil (champs de gestion « kind » / « raison sociale » toujours en tête).
        def sort_key(name):
            if name in ("kind", "company_name"):
                return -1
            d = self.defs.get(name[len("custom__"):] if name.startswith("custom__") else name)
            return d.order_for(profile) if d else 10**6

        self.fields = dict(sorted(self.fields.items(), key=lambda kv: sort_key(kv[0])))

    # --- Validation ---
    def clean_avs_number(self):
        value = self.cleaned_data.get("avs_number", "").strip()
        if not value:
            return ""
        formatted = services.format_avs(value)
        if not services.avs_is_valid(formatted):
            raise ValidationError("Numéro AVS invalide (13 chiffres commençant par 756, chiffre de contrôle incorrect).")
        return formatted

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("kind") == ContactKind.ENTREPRISE and not cleaned.get("company_name"):
            self.add_error("company_name", "Indiquez la raison sociale de l'entreprise.")
        if self.profile == Profile.MINEUR and self.instance.pk is None:
            if not (cleaned.get("email_parent1") or cleaned.get("phone_parent1")):
                self.add_error("email_parent1", "Au moins un moyen de contact du parent 1 est requis pour un mineur.")
        return cleaned

    def save(self, commit=True):
        member = super().save(commit=False)
        member.profile = self.profile
        member.training_days = self.cleaned_data.get("training_days", [])
        data = dict(member.custom_data or {})
        for d in self.custom_definitions:
            value = self.cleaned_data.get(f"custom__{d.key}")
            if hasattr(value, "isoformat"):
                value = value.isoformat()
            elif value is not None and d.field_type == FieldType.NUMBER:
                value = str(value)
            data[d.key] = value
        member.custom_data = data
        if commit:
            member.save()
            self.save_m2m()
        return member

    # --- Aide au rendu par sections ---
    def sections(self):
        """Regroupe les champs par section (mise en page du profil) pour le gabarit à deux colonnes."""
        order = list(F.SECTION_TITLES)
        grouped = {s: [] for s in order}
        for name in self.fields:
            if name in ("kind", "company_name"):
                grouped["general"].append(self[name])
                continue
            key = name[len("custom__"):] if name.startswith("custom__") else name
            d = self.defs.get(key)
            section = d.section_for(self.profile) if d else "meta"
            grouped.get(section, grouped["meta"]).append(self[name])
        return [(F.SECTION_TITLES[s], grouped[s]) for s in order if grouped[s]]


class ContactGroupForm(forms.ModelForm):
    class Meta:
        model = ContactGroup
        fields = ["name", "description", "is_course", "sort_order"]


class FieldDefinitionForm(forms.ModelForm):
    choices_text = forms.CharField(
        label="Options (une par ligne)", required=False, widget=forms.Textarea(attrs={"rows": 4})
    )
    profiles = forms.MultipleChoiceField(
        label="Profils concernés", choices=Profile.choices, widget=forms.CheckboxSelectMultiple, required=False,
        help_text="Aucune coche = tous les profils.",
    )

    class Meta:
        model = FieldDefinition
        fields = ["label", "field_type", "profiles", "is_sensitive", "is_active", "sort_order", "help_text"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial["choices_text"] = "\n".join(self.instance.choices or [])
            self.initial["profiles"] = self.instance.profiles or []
        self.fields["field_type"].choices = [
            c for c in FieldType.choices if c[0] not in ("WEEKDAYS",)
        ] + [("WEEKDAYS", "Jours de la semaine")]

    def clean(self):
        cleaned = super().clean()
        t = cleaned.get("field_type")
        opts = [line.strip() for line in cleaned.get("choices_text", "").splitlines() if line.strip()]
        if t in (FieldType.SELECT, FieldType.MULTISELECT) and not opts:
            self.add_error("choices_text", "Indiquez au moins une option pour une liste.")
        cleaned["choices"] = opts
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.choices = self.cleaned_data["choices"]
        obj.profiles = list(self.cleaned_data.get("profiles") or Profile.values)
        if not obj.key:
            base = services._ascii_slug(obj.label).replace("-", "_")[:50] or "champ"
            key, n = base, 1
            while FieldDefinition.objects.filter(key=key).exists():
                n += 1
                key = f"{base}_{n}"
            obj.key = key
        if commit:
            obj.save()
        return obj


class ValidateMemberForm(forms.Form):
    """Validation d'une inscription par le comité : infos de facturation non demandées dans le formulaire public."""

    training_mode = forms.ModelChoiceField(
        label="Modalité d'entraînement", queryset=TrainingMode.objects.filter(is_active=True), required=False,
        help_text="Choisie par la personne à l'inscription ; modifiable ici.",
    )
    tariff_bracket = forms.ModelChoiceField(label="Tranche tarifaire", queryset=TariffBracket.objects.all(), empty_label="— choisir —")
    family_discount = forms.BooleanField(
        label="Réduction famille (2ᵉ enfant et suivants) : -100 CHF", required=False,
    )
    entry_date = forms.DateField(label="Date d'entrée", widget=DATE_INPUT, required=False, help_text="Vide = aujourd'hui.")


class MassEditForm(forms.Form):
    """Modification de masse : une action appliquée à tous les contacts sélectionnés."""

    ACTIONS = [
        ("status", "Changer le statut"),
        ("add_group", "Ajouter au groupe"),
        ("remove_group", "Retirer du groupe"),
        ("training_mode", "Changer la modalité d'entraînement"),
        ("tariff_bracket", "Changer la tranche tarifaire"),
        ("exit_date", "Définir la date de sortie"),
    ]
    action = forms.ChoiceField(label="Action", choices=ACTIONS)
    status = forms.ChoiceField(label="Statut", choices=MemberStatus.choices, required=False)
    group = forms.ModelChoiceField(label="Groupe", queryset=ContactGroup.objects.all(), required=False)
    training_mode = forms.ModelChoiceField(label="Modalité", queryset=TrainingMode.objects.all(), required=False)
    tariff_bracket = forms.ModelChoiceField(label="Tranche", queryset=TariffBracket.objects.all(), required=False)
    exit_date = forms.DateField(label="Date de sortie", required=False, widget=DATE_INPUT)
    ids = forms.CharField(widget=forms.HiddenInput)

    def clean(self):
        cleaned = super().clean()
        action = cleaned.get("action")
        needed = {
            "status": "status", "add_group": "group", "remove_group": "group",
            "training_mode": "training_mode", "tariff_bracket": "tariff_bracket", "exit_date": "exit_date",
        }.get(action)
        if needed and not cleaned.get(needed):
            self.add_error(needed, "Valeur requise pour cette action.")
        return cleaned

    def member_ids(self):
        return [int(x) for x in self.cleaned_data["ids"].split(",") if x.strip().isdigit()]


class ImportForm(forms.Form):
    profile = forms.ChoiceField(label="Profil des fiches importées", choices=Profile.choices)
    file = forms.FileField(label="Fichier CSV", help_text="En-têtes = libellés des champs (ex. Prénom, Nom, Adresse…). Séparateur , ou ; détecté automatiquement.")
    status = forms.ChoiceField(label="Statut attribué", choices=MemberStatus.choices, initial=MemberStatus.ACTIF)
