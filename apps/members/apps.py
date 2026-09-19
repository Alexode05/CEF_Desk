from django.apps import AppConfig
from django.db.utils import DatabaseError


def _sync_builtin_fields(sender, **kwargs):
    """Après chaque migration : crée les champs natifs manquants (jamais d'écrasement)."""
    from . import fields

    try:
        fields.sync_builtin_fields()
    except DatabaseError:  # migration partielle : la table n'a pas encore son schéma final
        pass


class MembersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.members'

    def ready(self):
        from django.db.models.signals import post_migrate

        post_migrate.connect(_sync_builtin_fields, sender=self)
