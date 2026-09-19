from datetime import timedelta
from decimal import Decimal

from django import forms
from django.utils import timezone

from apps.members.models import ContactGroup, Member, MemberStatus


class BatchCreateForm(forms.Form):
    """Étape 1 : génération groupée pour un groupe (liste dynamique) ou une sélection de contacts."""

    label = forms.CharField(label="Libellé du lot", max_length=120, help_text="Ex. « Cotisations 2026-2027 — cours du lundi ».")
    group = forms.ModelChoiceField(
        label="Groupe de contacts", queryset=ContactGroup.objects.all(), required=False,
        help_text="Tous les membres actifs / licence de ce groupe.",
    )
    mailing_list = forms.ModelChoiceField(label="Liste de diffusion", queryset=None, required=False)
    ids = forms.CharField(widget=forms.HiddenInput, required=False)
    only_active = forms.BooleanField(
        label="Uniquement les membres au statut Actif ou Licence uniquement", initial=True, required=False
    )
    skip_already_invoiced = forms.BooleanField(
        label="Ignorer les membres déjà facturés pour la saison", initial=True, required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.mailing.models import MailingList

        self.fields["mailing_list"].queryset = MailingList.objects.all()

    def members(self):
        ids = [int(x) for x in (self.cleaned_data.get("ids") or "").split(",") if x.strip().isdigit()]
        group = self.cleaned_data.get("group")
        mlist = self.cleaned_data.get("mailing_list")
        if ids:
            qs = Member.objects.filter(pk__in=ids)
        elif mlist:
            qs = mlist.members()
        elif group:
            qs = group.members.all()
        else:
            return Member.objects.none()
        if self.cleaned_data.get("only_active"):
            qs = qs.filter(status__in=[MemberStatus.ACTIF, MemberStatus.LICENCE])
        return qs.exclude(kind="ENTREPRISE").order_by("last_name", "first_name")

    def clean(self):
        cleaned = super().clean()
        if not (cleaned.get("ids") or cleaned.get("group") or cleaned.get("mailing_list")):
            raise forms.ValidationError("Choisissez un groupe, une liste de diffusion ou une sélection de contacts.")
        return cleaned


class ManualInvoiceForm(forms.Form):
    """Facture indépendante : destinataire (un contact), montant et motif saisis à la main."""

    member = forms.ModelChoiceField(label="Destinataire", queryset=Member.objects.none(), empty_label="— choisir un contact —")
    amount = forms.DecimalField(label="Montant (CHF)", min_value=Decimal("0.01"), max_digits=8, decimal_places=2)
    description = forms.CharField(
        label="Motif de la facture", max_length=140,
        help_text="Apparaît sur la facture et dans la QR-facture (140 caractères max.). Ex. « Stage de Pâques 2027 ».",
    )
    issue_date = forms.DateField(label="Date d'émission", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    due_date = forms.DateField(label="Échéance", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    recipient_email = forms.EmailField(
        label="Email d'envoi", required=False, help_text="Vide = adresse de la fiche du contact."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.dashboard.models import ClubSettings

        members = Member.objects.order_by("last_name", "first_name", "company_name")
        self.fields["member"].queryset = members
        self.fields["member"].label_from_instance = lambda m: f"{m.display_name} — {m.member_id}"
        if not self.is_bound:
            today = timezone.localdate()
            self.fields["issue_date"].initial = today
            self.fields["due_date"].initial = today + timedelta(days=ClubSettings.load().invoice_due_days)

    def clean(self):
        cleaned = super().clean()
        issue, due = cleaned.get("issue_date"), cleaned.get("due_date")
        if issue and due and due < issue:
            self.add_error("due_date", "L'échéance ne peut pas précéder la date d'émission.")
        return cleaned


class MarkPaidForm(forms.Form):
    paid_at = forms.DateField(label="Date du paiement", required=False, widget=forms.DateInput(attrs={"type": "date"}))
