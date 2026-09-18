"""
Espace Stockage de fichiers — cahier des charges section 6.

Explorateur simple : dossiers/sous-dossiers (Club, Direction, Public au minimum),
upload, téléchargement, renommage, suppression. Reçoit aussi les factures PDF archivées
automatiquement et les copies de référence des modèles de formulaires.
"""
import os
import uuid

from django.conf import settings
from django.db import models


class Folder(models.Model):
    name = models.CharField("Nom", max_length=120)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="children")
    is_system = models.BooleanField("Dossier système", default=False, help_text="Non supprimable (Club, Direction, Public…).")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        unique_together = [("name", "parent")]
        verbose_name = "dossier"

    def __str__(self):
        return self.path

    @property
    def path(self):
        parts, node = [], self
        while node is not None:
            parts.append(node.name)
            node = node.parent
        return "/".join(reversed(parts))

    def ancestors(self):
        out, node = [], self.parent
        while node is not None:
            out.append(node)
            node = node.parent
        return list(reversed(out))

    @classmethod
    def ensure_path(cls, path):
        """Crée (si besoin) et renvoie le dossier `A/B/C`."""
        parent = None
        for part in [p for p in path.split("/") if p]:
            parent, _ = cls.objects.get_or_create(name=part, parent=parent)
        return parent


def stored_file_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()[:10]
    return f"documents/{uuid.uuid4().hex}{ext}"


class StoredFile(models.Model):
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, related_name="files")
    name = models.CharField("Nom du fichier", max_length=200)
    file = models.FileField(upload_to=stored_file_upload_to)
    size = models.PositiveBigIntegerField(default=0)
    content_type = models.CharField(max_length=120, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    is_system = models.BooleanField(default=False, help_text="Déposé automatiquement (facture archivée, modèle de formulaire).")

    class Meta:
        ordering = ["name"]
        verbose_name = "fichier"

    def __str__(self):
        return self.name

    @property
    def extension(self):
        return os.path.splitext(self.name)[1].lower().lstrip(".")

    @property
    def icon(self):
        ext = self.extension
        return {
            "pdf": "bi-file-earmark-pdf",
            "doc": "bi-file-earmark-word", "docx": "bi-file-earmark-word",
            "xls": "bi-file-earmark-excel", "xlsx": "bi-file-earmark-excel", "csv": "bi-file-earmark-spreadsheet",
            "png": "bi-file-earmark-image", "jpg": "bi-file-earmark-image", "jpeg": "bi-file-earmark-image",
            "zip": "bi-file-earmark-zip", "json": "bi-file-earmark-code", "txt": "bi-file-earmark-text",
        }.get(ext, "bi-file-earmark")

    def save(self, *args, **kwargs):
        if self.file and not self.size:
            try:
                self.size = self.file.size
            except Exception:
                pass
        super().save(*args, **kwargs)
