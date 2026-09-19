from django import forms
from stdnum import iban as iban_mod

from .models import ClubSettings


class ClubSettingsForm(forms.ModelForm):
    class Meta:
        model = ClubSettings
        fields = [
            "club_name",
            "street",
            "postal_code",
            "city",
            "country",
            "logo",
            "creditor_name",
            "iban",
            "treasurer_email",
            "secretariat_email",
            "president_email",
            "vice_president_email",
            "auditor_email",
            "season_start_month",
            "invoice_due_days",
            "reminder_delay_days",
            "invoice_email_subject",
            "invoice_email_body",
            "reminder_email_subject",
            "reminder_email_body",
        ]
        widgets = {
            "invoice_email_body": forms.Textarea(attrs={"rows": 9}),
            "reminder_email_body": forms.Textarea(attrs={"rows": 8}),
        }

    def clean_iban(self):
        raw = self.cleaned_data["iban"].replace(" ", "").upper()
        if not raw.startswith(("CH", "LI")):
            raise forms.ValidationError("L'IBAN doit être suisse (CH) ou liechtensteinois (LI) pour une QR-facture.")
        if not iban_mod.is_valid(raw):
            raise forms.ValidationError("IBAN invalide (chiffre de contrôle incorrect).")
        return raw

    def clean_country(self):
        return self.cleaned_data["country"].strip().upper()


class TodoForm(forms.Form):
    text = forms.CharField(max_length=300, widget=forms.TextInput(attrs={"placeholder": "Nouvelle tâche…", "class": "form-control"}))
