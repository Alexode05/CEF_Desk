"""
Module Mailing groupé — cahier des charges section 8.

Listes de diffusion dynamiques (= un groupe de contacts, mise à jour automatique), statiques
(sélection figée) ou automatiques « à facturer » (listes système, cf. billing_lists.py). Servent aux
emails groupés et comme base de génération/envoi groupé des factures.
"""
from django.conf import settings
from django.db import models

from apps.members.models import ContactGroup, Member


class MailingList(models.Model):
    class Kind(models.TextChoices):
        DYNAMIC = "DYNAMIC", "Dynamique (suit un groupe)"
        STATIC = "STATIC", "Statique (sélection figée)"
        BILLING = "BILLING", "Automatique (à facturer)"

    class BillingRule(models.TextChoices):
        MEMBERSHIP = "MEMBERSHIP", "Inscriptions définitives à facturer"
        TRIAL = "TRIAL", "Cours d'essai à facturer"

    name = models.CharField("Nom", max_length=100, unique=True)
    kind = models.CharField("Type", max_length=8, choices=Kind.choices, default=Kind.DYNAMIC)
    group = models.ForeignKey(ContactGroup, verbose_name="Groupe suivi", null=True, blank=True, on_delete=models.SET_NULL)
    static_members = models.ManyToManyField(Member, verbose_name="Contacts", blank=True, related_name="mailing_lists")
    billing_rule = models.CharField(
        "Règle (listes automatiques)", max_length=10, choices=BillingRule.choices, blank=True,
        help_text="Uniquement pour les deux listes système « à facturer ».",
    )
    description = models.CharField("Description", max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["name"]
        verbose_name = "liste de diffusion"
        verbose_name_plural = "listes de diffusion"

    def __str__(self):
        return self.name

    @property
    def is_billing(self):
        """Liste système « à facturer » : contenu calculé automatiquement, non modifiable ni supprimable."""
        return self.kind == self.Kind.BILLING

    def members(self):
        if self.is_billing:
            from .billing_lists import members_for_rule

            return members_for_rule(self.billing_rule)
        if self.kind == self.Kind.DYNAMIC and self.group_id:
            return self.group.members.all()
        return self.static_members.all()

    def recipients(self):
        """Liste dédoublonnée de (membre, email) — emails principaux uniquement."""
        seen, out = set(), []
        for m in self.members():
            email = m.primary_email
            if email and email.lower() not in seen:
                seen.add(email.lower())
                out.append((m, email))
        return out


class Campaign(models.Model):
    """Email groupé envoyé (historique)."""

    subject = models.CharField("Sujet", max_length=200)
    body = models.TextField("Message")
    mailing_list = models.ForeignKey(MailingList, null=True, blank=True, on_delete=models.SET_NULL)
    recipients_count = models.PositiveIntegerField(default=0)
    errors_count = models.PositiveIntegerField(default=0)
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    attachment = models.FileField("Pièce jointe", upload_to="mailing/%Y/", blank=True)

    class Meta:
        ordering = ["-sent_at"]
        verbose_name = "envoi groupé"
        verbose_name_plural = "envois groupés"

    def __str__(self):
        return self.subject
