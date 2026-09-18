from django import forms

from apps.members.models import Member

from .models import MailingList


class MailingListForm(forms.ModelForm):
    ids = forms.CharField(widget=forms.HiddenInput, required=False)

    class Meta:
        model = MailingList
        fields = ["name", "kind", "group", "description"]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("kind") == MailingList.Kind.DYNAMIC and not cleaned.get("group"):
            self.add_error("group", "Choisissez le groupe suivi par cette liste dynamique.")
        return cleaned

    def member_ids(self):
        return [int(x) for x in (self.cleaned_data.get("ids") or "").split(",") if x.strip().isdigit()]


class CampaignForm(forms.Form):
    mailing_list = forms.ModelChoiceField(label="Liste de diffusion", queryset=MailingList.objects.all())
    subject = forms.CharField(label="Sujet", max_length=200)
    body = forms.CharField(label="Message", widget=forms.Textarea(attrs={"rows": 10}), help_text="Variables : {prenom}, {nom}, {club}, {saison}.")
    attachment = forms.FileField(label="Pièce jointe (optionnelle)", required=False)
    exclude_ids = forms.CharField(widget=forms.HiddenInput, required=False)
    cc_treasurer = forms.BooleanField(label="Mettre le trésorier en copie", required=False, initial=False)

    def excluded(self):
        return {int(x) for x in (self.cleaned_data.get("exclude_ids") or "").split(",") if x.strip().isdigit()}
