from django.conf import settings
from django.db import models
from django.utils import timezone


class AccountProfile(models.Model):
    """Informations de compte propres à CEF Desk : date de vérification de l'adresse email."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="account_profile")
    email_verified_at = models.DateTimeField("Email vérifié le", null=True, blank=True)

    class Meta:
        verbose_name = "profil de compte"
        verbose_name_plural = "profils de compte"

    def __str__(self):
        return f"Profil de {self.user}"

    @property
    def email_verified(self):
        return self.email_verified_at is not None

    def mark_verified(self):
        self.email_verified_at = timezone.now()
        self.save(update_fields=["email_verified_at"])

    @classmethod
    def for_user(cls, user):
        profile, _ = cls.objects.get_or_create(user=user)
        return profile
