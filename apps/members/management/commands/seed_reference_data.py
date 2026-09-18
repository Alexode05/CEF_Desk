"""
Données de référence initiales (idempotent) : champs natifs, groupes par défaut,
modalités d'entraînement, tranches tarifaires, grille de tarifs vide, dossiers de stockage,
paramètres du club.

    python manage.py seed_reference_data
"""
from django.core.management.base import BaseCommand

from apps.billing.models import Tariff
from apps.dashboard.models import ClubSettings
from apps.documents.models import Folder
from apps.members import fields as F
from apps.members.models import ContactGroup, TariffBracket, TrainingMode

DEFAULT_GROUPS = [
    ("Cours 1", "Créneau de cours n° 1 (à renommer)", True, 10),
    ("Cours 2", "Créneau de cours n° 2 (à renommer)", True, 20),
    ("Cours 3", "Créneau de cours n° 3 (à renommer)", True, 30),
    ("Cours 4", "Créneau de cours n° 4 (à renommer)", True, 40),
    ("Cours 5", "Créneau de cours n° 5 (à renommer)", True, 50),
    ("Essais", "Personnes en cours d'essai", False, 60),
    ("Comité", "Membres du comité", False, 70),
]

TRAINING_MODES = [
    ("1 jour par semaine", 1, 10),
    ("2 jours par semaine", 2, 20),
    ("3 jours par semaine", 3, 30),
]

BRACKETS = [
    ("P'tit Zorros", 10),
    ("Moins de 20 ans", 20),
    ("Dès 20 ans", 30),
    ("Étudiant entre 20 et 25 ans", 40),
]

FOLDERS = ["Club", "Direction", "Public", "Club/Factures", "Club/Formulaires"]


class Command(BaseCommand):
    help = "Crée les données de référence initiales (idempotent)."

    def handle(self, *args, **options):
        F.sync_builtin_fields()
        self.stdout.write("Champs natifs synchronisés.")

        for name, desc, is_course, order in DEFAULT_GROUPS:
            ContactGroup.objects.get_or_create(name=name, defaults={"description": desc, "is_course": is_course, "sort_order": order})
        for name, days, order in TRAINING_MODES:
            TrainingMode.objects.get_or_create(name=name, defaults={"days_per_week": days, "sort_order": order})
        for name, order in BRACKETS:
            TariffBracket.objects.get_or_create(name=name, defaults={"sort_order": order})
        for mode in TrainingMode.objects.all():
            for bracket in TariffBracket.objects.all():
                Tariff.objects.get_or_create(training_mode=mode, bracket=bracket)
        self.stdout.write("Groupes, modalités, tranches et grille tarifaire (montants à définir) créés.")

        for path in FOLDERS:
            folder = Folder.ensure_path(path)
            if "/" not in path:
                folder.is_system = True
                folder.save(update_fields=["is_system"])
        self.stdout.write("Dossiers Club / Direction / Public créés.")

        ClubSettings.load()
        self.stdout.write(self.style.SUCCESS("Données de référence prêtes."))
