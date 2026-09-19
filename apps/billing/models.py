"""
Module Comptabilité / Facturation — cahier des charges section 5.

Périmètre V1 : cotisations uniquement. Barème = modalités × tranches ; facture par membre
avec QR-facture (générée via la bibliothèque `qrbill`), relance automatique, validation
manuelle du paiement, archivage PDF dans l'espace de stockage.
"""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.members.models import Member, TariffBracket, TrainingMode


class Tariff(models.Model):
    """Grille tarifaire : montant pour une (modalité, tranche). `amount` vide = à définir."""

    training_mode = models.ForeignKey(TrainingMode, on_delete=models.CASCADE, related_name="tariffs")
    bracket = models.ForeignKey(TariffBracket, on_delete=models.CASCADE, related_name="tariffs")
    amount = models.DecimalField("Montant (CHF)", max_digits=8, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = [("training_mode", "bracket")]
        verbose_name = "tarif"

    def __str__(self):
        return f"{self.training_mode} / {self.bracket} : {self.amount if self.amount is not None else 'à définir'}"

    @classmethod
    def amount_for(cls, training_mode_id, bracket_id):
        row = cls.objects.filter(training_mode_id=training_mode_id, bracket_id=bracket_id).first()
        return row.amount if row and row.amount is not None else None


class InvoiceStatus(models.TextChoices):
    GENEREE = "GENEREE", "Générée (non envoyée)"
    ENVOYEE = "ENVOYEE", "Envoyée"
    RELANCEE = "RELANCEE", "Relancée"
    PAYEE = "PAYEE", "Payée"
    ANNULEE = "ANNULEE", "Annulée"


class InvoiceKind(models.TextChoices):
    COTISATION = "COTISATION", "Cotisation"
    MANUELLE = "MANUELLE", "Facture manuelle"


class InvoiceQuerySet(models.QuerySet):
    def unpaid(self):
        return self.filter(status__in=[InvoiceStatus.GENEREE, InvoiceStatus.ENVOYEE, InvoiceStatus.RELANCEE])

    def sent(self):
        return self.filter(status__in=[InvoiceStatus.ENVOYEE, InvoiceStatus.RELANCEE])


class InvoiceBatch(models.Model):
    """Lot de génération groupée (étape 1) — l'envoi (étape 2) se fait depuis le même écran."""

    label = models.CharField("Libellé", max_length=120)
    season = models.CharField("Saison", max_length=9)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    source_description = models.CharField("Source", max_length=200, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "lot de factures"
        verbose_name_plural = "lots de factures"

    def __str__(self):
        return self.label

    @property
    def total(self):
        return sum((i.amount for i in self.invoices.exclude(status=InvoiceStatus.ANNULEE)), Decimal("0.00"))


class Invoice(models.Model):
    objects = InvoiceQuerySet.as_manager()

    number = models.CharField("Numéro", max_length=20, unique=True)
    kind = models.CharField("Type", max_length=12, choices=InvoiceKind.choices, default=InvoiceKind.COTISATION)
    member = models.ForeignKey(Member, on_delete=models.PROTECT, related_name="invoices")
    batch = models.ForeignKey(InvoiceBatch, null=True, blank=True, on_delete=models.SET_NULL, related_name="invoices")
    season = models.CharField("Saison", max_length=9)

    # Snapshot de la facturation (la fiche peut changer ensuite).
    training_mode_label = models.CharField("Modalité", max_length=80, blank=True)
    bracket_label = models.CharField("Tranche", max_length=80, blank=True)
    base_amount = models.DecimalField("Montant de base", max_digits=8, decimal_places=2)
    family_discount = models.DecimalField("Réduction famille", max_digits=8, decimal_places=2, default=Decimal("0.00"))
    amount = models.DecimalField("Montant", max_digits=8, decimal_places=2)
    description = models.CharField("Motif", max_length=140)

    # Débiteur (snapshot pour la QR-facture)
    debtor_name = models.CharField(max_length=70)
    debtor_street = models.CharField(max_length=70, blank=True)
    debtor_postal_code = models.CharField(max_length=16, blank=True)
    debtor_city = models.CharField(max_length=35, blank=True)
    debtor_country = models.CharField(max_length=2, default="CH")
    recipient_email = models.EmailField("Email destinataire", blank=True)

    reference = models.CharField("Référence de paiement", max_length=27, blank=True)
    issue_date = models.DateField("Date d'émission")
    due_date = models.DateField("Échéance")
    status = models.CharField("Statut", max_length=10, choices=InvoiceStatus.choices, default=InvoiceStatus.GENEREE)

    sent_at = models.DateTimeField("Envoyée le", null=True, blank=True)
    reminded_at = models.DateTimeField("Relancée le", null=True, blank=True)
    reminder_count = models.PositiveSmallIntegerField("Nombre de relances", default=0)
    paid_at = models.DateField("Payée le", null=True, blank=True)
    paid_marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="invoices_marked_paid"
    )

    pdf = models.FileField("PDF", upload_to="factures/%Y/", blank=True)
    archived_file = models.ForeignKey(
        "documents.StoredFile", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-issue_date", "-number"]
        verbose_name = "facture"

    def __str__(self):
        return f"Facture {self.number}"

    @property
    def is_manual(self):
        return self.kind == InvoiceKind.MANUELLE

    @property
    def is_unpaid(self):
        return self.status in (InvoiceStatus.GENEREE, InvoiceStatus.ENVOYEE, InvoiceStatus.RELANCEE)

    @property
    def is_overdue(self):
        return self.is_unpaid and self.due_date < timezone.localdate()

    @property
    def next_reminder_date(self):
        """Date de la prochaine relance automatique (None si payée/annulée/non envoyée)."""
        if not self.is_unpaid or self.status == InvoiceStatus.GENEREE:
            return None
        from apps.dashboard.models import ClubSettings

        delay = ClubSettings.load().reminder_delay_days
        anchor = timezone.localdate(self.reminded_at) if self.reminded_at else self.issue_date
        return anchor + timedelta(days=delay)

    @property
    def reminder_is_due(self):
        nxt = self.next_reminder_date
        return nxt is not None and nxt <= timezone.localdate()

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("billing:invoice_detail", args=[self.pk])


class EmailLog(models.Model):
    """Journal des emails envoyés (factures, relances, mailings)."""

    KINDS = [("facture", "Facture"), ("relance", "Relance"), ("mailing", "Mailing"), ("notification", "Notification")]
    kind = models.CharField(max_length=14, choices=KINDS)
    to = models.CharField(max_length=300)
    cc = models.CharField(max_length=300, blank=True)
    subject = models.CharField(max_length=300)
    invoice = models.ForeignKey(Invoice, null=True, blank=True, on_delete=models.SET_NULL, related_name="emails")
    member = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name="emails")
    ok = models.BooleanField(default=True)
    error = models.TextField(blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-sent_at"]
        verbose_name = "email envoyé"
        verbose_name_plural = "emails envoyés"

    def __str__(self):
        return f"{self.get_kind_display()} → {self.to}"
