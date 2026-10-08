"""Les comptes existants avant la vérification d'email (créés sous l'ancien régime A2F) sont considérés comme vérifiés."""
from django.conf import settings
from django.db import migrations
from django.utils import timezone


def forwards(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    AccountProfile = apps.get_model("accounts", "AccountProfile")
    now = timezone.now()
    for user in User.objects.filter(is_active=True):
        AccountProfile.objects.update_or_create(user=user, defaults={"email_verified_at": now})


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
