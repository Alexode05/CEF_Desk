"""
Sauvegarde automatique : base de données + fichiers (espace de stockage, factures archivées).

    python manage.py backup

Produit `backups/cefdesk-AAAAMMJJ-HHMMSS.zip` contenant :
  - db.sqlite3 (copie cohérente via l'API de sauvegarde SQLite) OU un dump `pg_dump` (PostgreSQL)
  - le dossier media/ complet
Puis supprime les archives plus anciennes que CEF_BACKUP_KEEP_DAYS (30 jours par défaut).

À planifier quotidiennement (Planificateur de tâches Windows en local ; cron chez l'hébergeur).
"""
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Sauvegarde la base de données et les fichiers dans un zip horodaté."

    def handle(self, *args, **options):
        backup_dir = Path(settings.BACKUP_DIR)
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = backup_dir / f"cefdesk-{stamp}.zip"
        db = settings.DATABASES["default"]

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            if db["ENGINE"].endswith("sqlite3"):
                src = sqlite3.connect(str(db["NAME"]))
                dst = sqlite3.connect(str(tmp / "db.sqlite3"))
                with dst:
                    src.backup(dst)
                src.close()
                dst.close()
                db_file = tmp / "db.sqlite3"
            else:
                db_file = tmp / "db.dump"
                env = os.environ.copy()
                env["PGPASSWORD"] = db.get("PASSWORD", "")
                cmd = ["pg_dump", "-Fc", "-h", db.get("HOST") or "localhost", "-p", str(db.get("PORT") or 5432), "-U", db["USER"], "-f", str(db_file), db["NAME"]]
                try:
                    subprocess.run(cmd, check=True, env=env, capture_output=True)
                except (OSError, subprocess.CalledProcessError) as exc:
                    raise CommandError(f"pg_dump a échoué : {exc}") from exc

            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(db_file, db_file.name)
                media = Path(settings.MEDIA_ROOT)
                if media.exists():
                    for path in media.rglob("*"):
                        if path.is_file():
                            zf.write(path, Path("media") / path.relative_to(media))

        self.stdout.write(self.style.SUCCESS(f"Sauvegarde créée : {target} ({target.stat().st_size // 1024} Ko)"))

        cutoff = time.time() - settings.BACKUP_KEEP_DAYS * 86400
        removed = 0
        for old in backup_dir.glob("cefdesk-*.zip"):
            if old.stat().st_mtime < cutoff:
                old.unlink()
                removed += 1
        if removed:
            self.stdout.write(f"{removed} ancienne(s) sauvegarde(s) supprimée(s) (> {settings.BACKUP_KEEP_DAYS} jours).")
