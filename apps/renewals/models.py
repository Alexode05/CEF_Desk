"""
Passage à la saison suivante (demande d'Alex du 08.10.2026).

Le comité lance, depuis le tableau de bord, un « passage de saison » : chaque membre actif reçoit
un email (à l'adresse de facturation, parent 1 pour un mineur) avec un lien personnel vers un
formulaire qui affiche ses données actuelles, modifiables, et un bouton « démission ».

- Données confirmées / corrigées → demande « à valider » (comme une inscription) : le comité
  relit les changements et les applique à la fiche.
- Démission → demande « à confirmer » : le comité confirme, la fiche est alors supprimée
  (ses factures sont conservées), ou décide de garder la fiche.
"""
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.members.models import Member

LINK_VALIDITY_DAYS = 60


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


class SeasonRollover(models.Model):
    target_season = models.CharField("Saison préparée", max_length=9)
    subject = models.CharField("Sujet de l'email", max_length=200)
    body = models.TextField("Texte de l'email")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "passage de saison"
        verbose_name_plural = "passages de saison"

    def __str__(self):
        return f"Passage à la saison {self.target_season}"

    def count(self, *statuses):
        return self.requests.filter(status__in=statuses).count()


class RenewalRequest(models.Model):
    """Invitation envoyée à un membre et sa réponse."""

    class Status(models.TextChoices):
        SENT = "SENT", "Invitation envoyée — sans réponse"
        TO_VALIDATE = "TO_VALIDATE", "Données envoyées — à valider"
        RESIGNATION = "RESIGNATION", "Démission annoncée — à confirmer"
        VALIDATED = "VALIDATED", "Données validées"
        RESIGNED = "RESIGNED", "Démission confirmée — fiche supprimée"
        KEPT = "KEPT", "Démission non confirmée — fiche conservée"
        FAILED = "FAILED", "Envoi impossible"

    TO_PROCESS = (Status.TO_VALIDATE, Status.RESIGNATION)

    rollover = models.ForeignKey(SeasonRollover, on_delete=models.CASCADE, related_name="requests")
    member = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name="renewal_requests")
    member_name = models.CharField("Membre", max_length=160)  # conservé si la fiche est supprimée
    email = models.EmailField("Email utilisé", blank=True)
    token_hash = models.CharField(max_length=64, unique=True)  # seul le hachage est stocké, jamais le lien
    expires_at = models.DateTimeField("Lien valable jusqu'au")
    status = models.CharField("Statut", max_length=12, choices=Status.choices, default=Status.SENT)
    sent_at = models.DateTimeField(null=True, blank=True)
    send_error = models.TextField(blank=True)
    proposed = models.JSONField("Valeurs modifiées", default=dict, blank=True)
    changes = models.JSONField("Changements (affichage)", default=list, blank=True)
    remark = models.TextField("Remarque du membre", blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["member_name"]
        verbose_name = "réponse de passage de saison"
        verbose_name_plural = "réponses de passage de saison"
        constraints = [models.UniqueConstraint(fields=["rollover", "member"], name="one_request_per_member_and_rollover")]

    def __str__(self):
        return f"{self.member_name} — {self.rollover.target_season}"

    def new_token(self):
        """Génère un nouveau lien (l'ancien cesse de fonctionner) ; renvoie le jeton en clair, à envoyer par email."""
        token = secrets.token_urlsafe(32)
        self.token_hash = hash_token(token)
        self.expires_at = timezone.now() + timedelta(days=LINK_VALIDITY_DAYS)
        return token

    @property
    def is_open(self):
        """Le membre peut encore répondre."""
        return self.status == self.Status.SENT and self.member_id is not None and self.expires_at > timezone.now()

    @property
    def to_process(self):
        return self.status in self.TO_PROCESS

    @classmethod
    def find(cls, token):
        return cls.objects.select_related("member", "rollover").filter(token_hash=hash_token(token or "")).first()
