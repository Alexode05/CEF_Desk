"""
Tableau de bord + paramètres centraux du club.

`ClubSettings` est l'unique point de configuration des coordonnées du club
(créancier des QR-factures), des adresses trésorier/secrétariat et de la saison.
Les valeurs bancaires par défaut sont des PLACEHOLDERS clairement identifiés,
à remplacer par Alex depuis l'écran « Paramètres du club » avant la mise en production.
"""
from datetime import date

from django.conf import settings
from django.db import models

# IBAN d'exemple publié par SIX dans ses guides (QR-IBAN, IID 31999) — fictif.
PLACEHOLDER_IBAN = "CH4431999123000889012"
PLACEHOLDER_MARKER = "[PLACEHOLDER]"


class ClubSettings(models.Model):
    """Singleton (une seule ligne, id=1)."""

    club_name = models.CharField("Nom du club", max_length=120, default="Cercle d'Escrime de Founex")
    street = models.CharField("Rue et numéro", max_length=120, default=f"{PLACEHOLDER_MARKER} Rue de l'Escrime 1")
    postal_code = models.CharField("Code postal", max_length=16, default="1297")
    city = models.CharField("Ville", max_length=80, default="Founex")
    country = models.CharField("Pays (code ISO)", max_length=2, default="CH")
    logo = models.ImageField("Logo (en-tête des factures)", upload_to="club/", blank=True, null=True)

    # --- Coordonnées bancaires (créancier des QR-factures) ---
    creditor_name = models.CharField(
        "Nom du titulaire du compte",
        max_length=70,
        default=f"{PLACEHOLDER_MARKER} Cercle d'Escrime de Founex",
        help_text="Tel qu'il apparaît sur le compte bancaire (max. 70 caractères, norme QR-facture).",
    )
    iban = models.CharField(
        "IBAN ou QR-IBAN",
        max_length=34,
        default=PLACEHOLDER_IBAN,
        help_text="Avec un QR-IBAN, une référence QR est générée ; avec un IBAN classique, une référence SCOR.",
    )

    # --- Adresses email du comité ---
    treasurer_email = models.EmailField(
        "Email du trésorier (Cc systématique des factures)", blank=True, default="tresorier@example.invalid"
    )
    secretariat_email = models.EmailField(
        "Email du secrétariat (notifications d'inscription)", blank=True, default="secretariat@example.invalid"
    )

    # --- Saison et facturation ---
    season_start_month = models.PositiveSmallIntegerField(
        "Mois de début de saison", default=9, help_text="9 = septembre. Sert au calcul de la saison courante et des catégories d'âge."
    )
    invoice_due_days = models.PositiveSmallIntegerField("Délai de paiement (jours)", default=30)
    reminder_delay_days = models.PositiveSmallIntegerField(
        "Délai avant relance (jours)", default=30, help_text="Relance automatique si la facture n'est pas payée après ce délai."
    )
    invoice_email_subject = models.CharField(
        "Sujet de l'email de facture",
        max_length=200,
        default="Cotisation {saison} — {prenom} {nom}",
    )
    invoice_email_body = models.TextField(
        "Texte de l'email de facture",
        default=(
            "Bonjour,\n\n"
            "Vous trouverez en pièce jointe la facture de cotisation pour la saison {saison} "
            "concernant {prenom} {nom} ({modalite}).\n\n"
            "Montant : CHF {montant}\n"
            "Échéance : {echeance}\n\n"
            "La facture comporte une QR-facture que vous pouvez scanner avec votre application bancaire.\n\n"
            "Avec nos salutations sportives,\n"
            "Le comité du Cercle d'Escrime de Founex"
        ),
        help_text="Variables disponibles : {saison}, {prenom}, {nom}, {modalite}, {montant}, {echeance}, {numero}.",
    )
    reminder_email_subject = models.CharField(
        "Sujet de l'email de relance", max_length=200, default="Rappel — cotisation {saison} — {prenom} {nom}"
    )
    reminder_email_body = models.TextField(
        "Texte de l'email de relance",
        default=(
            "Bonjour,\n\n"
            "Sauf erreur de notre part, la facture n° {numero} (cotisation {saison}, {prenom} {nom}) "
            "d'un montant de CHF {montant}, échue le {echeance}, n'a pas encore été réglée.\n\n"
            "Vous la trouverez à nouveau en pièce jointe. Si le paiement a été effectué entre-temps, "
            "merci de ne pas tenir compte de ce rappel.\n\n"
            "Avec nos salutations sportives,\n"
            "Le comité du Cercle d'Escrime de Founex"
        ),
    )

    class Meta:
        verbose_name = "paramètres du club"
        verbose_name_plural = "paramètres du club"

    def __str__(self):
        return "Paramètres du club"

    def save(self, *args, **kwargs):
        self.pk = 1
        self.iban = self.iban.replace(" ", "").upper()
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    # --- Helpers ---
    @property
    def bank_details_are_placeholder(self):
        return (
            self.iban.replace(" ", "").upper() == PLACEHOLDER_IBAN
            or PLACEHOLDER_MARKER in self.creditor_name
            or PLACEHOLDER_MARKER in self.street
        )

    @property
    def iban_formatted(self):
        raw = self.iban.replace(" ", "")
        return " ".join(raw[i : i + 4] for i in range(0, len(raw), 4))

    @property
    def is_qr_iban(self):
        raw = self.iban.replace(" ", "")
        if len(raw) < 9 or not raw[4:9].isdigit():
            return False
        return 30000 <= int(raw[4:9]) <= 31999

    def season_reference_year(self, on_date=None):
        """Année civile de FIN de la saison en cours (saison 2026-2027 -> 2027)."""
        on_date = on_date or date.today()
        return on_date.year + 1 if on_date.month >= self.season_start_month else on_date.year

    def current_season_label(self, on_date=None):
        end = self.season_reference_year(on_date)
        return f"{end - 1}-{end}"


class DashboardNote(models.Model):
    """Post-it partagé : un seul bloc de texte libre, modifiable par tout le comité."""

    content = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name = "notes du tableau de bord"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class TodoItem(models.Model):
    text = models.CharField("Tâche", max_length=300)
    is_done = models.BooleanField("Terminée", default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="todos_created"
    )
    done_at = models.DateTimeField(null=True, blank=True)
    done_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="todos_done"
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="todos_updated"
    )

    class Meta:
        ordering = ["is_done", "-created_at"]
        verbose_name = "tâche"

    def __str__(self):
        return self.text


class TodoLog(models.Model):
    """Traçabilité de la to-do liste : qui a fait quoi, quand."""

    ACTIONS = [
        ("create", "Création"),
        ("done", "Cochée"),
        ("undone", "Décochée"),
        ("edit", "Modification"),
        ("delete", "Suppression"),
    ]
    todo_text = models.CharField(max_length=300)
    action = models.CharField(max_length=10, choices=ACTIONS)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-at"]

    def __str__(self):
        return f"{self.get_action_display()} — {self.todo_text}"
