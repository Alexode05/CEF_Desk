"""Dépôt programmatique de fichiers dans l'espace de stockage (archivage automatique)."""
from django.core.files.base import ContentFile

from .models import Folder, StoredFile


def store_generated_file(folder_path, filename, content: bytes, content_type="application/octet-stream", user=None):
    """Dépose `content` sous `folder_path/filename` (remplace un fichier système homonyme)."""
    folder = Folder.ensure_path(folder_path)
    existing = StoredFile.objects.filter(folder=folder, name=filename, is_system=True).first()
    if existing:
        existing.file.delete(save=False)
        existing.delete()
    stored = StoredFile(folder=folder, name=filename, content_type=content_type, uploaded_by=user, is_system=True, size=len(content))
    stored.file.save(filename, ContentFile(content), save=False)
    stored.save()
    return stored
