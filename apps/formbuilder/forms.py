from django import forms

from apps.members import fields as F
from apps.members.models import FieldDefinition

from .models import FormDefinition, FormField


class FormDefinitionForm(forms.ModelForm):
    class Meta:
        model = FormDefinition
        fields = ["name", "slug", "is_active", "profile", "intro_text", "privacy_notice", "success_message", "default_groups", "notify_email"]
        widgets = {
            "intro_text": forms.Textarea(attrs={"rows": 4}),
            "privacy_notice": forms.Textarea(attrs={"rows": 4}),
            "success_message": forms.Textarea(attrs={"rows": 2}),
            "default_groups": forms.CheckboxSelectMultiple,
        }


def public_field_definitions():
    """Champs de la fiche proposables dans un formulaire public (jamais les champs réservés au comité)."""
    return [d for d in FieldDefinition.objects.filter(is_active=True) if d.key not in F.NOT_IN_PUBLIC_FORMS]


class AddFieldForm(forms.Form):
    kind = forms.ChoiceField(label="Type d'élément", choices=FormField.Kind.choices, initial=FormField.Kind.FIELD)
    field_definition = forms.ModelChoiceField(label="Champ de la fiche", queryset=FieldDefinition.objects.none(), required=False)
    text = forms.CharField(label="Texte du bloc", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    required = forms.BooleanField(label="Obligatoire", required=False, initial=True)

    def __init__(self, *args, form_definition=None, **kwargs):
        super().__init__(*args, **kwargs)
        used = set(form_definition.fields.filter(kind="FIELD").values_list("field_definition_id", flat=True)) if form_definition else set()
        ids = [d.pk for d in public_field_definitions() if d.pk not in used]
        self.fields["field_definition"].queryset = FieldDefinition.objects.filter(pk__in=ids)

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("kind")
        if kind == FormField.Kind.FIELD and not cleaned.get("field_definition"):
            self.add_error("field_definition", "Choisissez un champ.")
        if kind == FormField.Kind.TEXT and not cleaned.get("text"):
            self.add_error("text", "Saisissez le texte.")
        return cleaned


class FormFieldEditForm(forms.ModelForm):
    class Meta:
        model = FormField
        fields = ["label", "help_text", "text", "required", "condition_field", "condition_operator", "condition_value"]
        widgets = {"text": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ff = self.instance
        qs = FormField.objects.filter(form=ff.form).exclude(pk=ff.pk).exclude(kind=FormField.Kind.TEXT)
        self.fields["condition_field"].queryset = qs
        self.fields["condition_field"].required = False
        self.fields["condition_field"].empty_label = "— toujours affiché —"
        if ff.kind != FormField.Kind.TEXT:
            del self.fields["text"]
        else:
            del self.fields["required"]
        if ff.kind == FormField.Kind.PROFILE:
            self.fields["required"].disabled = True
