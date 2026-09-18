"""
Relances automatiques : envoie un rappel (PDF joint, trésorier en Cc) pour chaque facture
envoyée, impayée, dont le délai de relance (Paramètres du club, 30 jours par défaut) est écoulé.

À planifier une fois par jour (Planificateur de tâches Windows / cron) :
    python manage.py send_reminders
"""
from django.core.management.base import BaseCommand

from apps.billing import services


class Command(BaseCommand):
    help = "Envoie les relances de paiement dues."

    def handle(self, *args, **options):
        sent, errors = services.run_due_reminders()
        for inv in sent:
            self.stdout.write(f"Relance envoyée : {inv.number} ({inv.member.display_name})")
        for e in errors:
            self.stderr.write(f"Erreur : {e}")
        self.stdout.write(self.style.SUCCESS(f"{len(sent)} relance(s) envoyée(s), {len(errors)} erreur(s)."))
