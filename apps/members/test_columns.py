"""Colonnes de la liste des contacts : le choix confirmé s'applique tout de suite, même avec une vue ouverte."""
import re

from django.test import TestCase, override_settings

from apps.members import fields as F
from apps.members.models import Member, MemberStatus, Role, SavedView, UserListPreference
from apps.members.tests import verified_client


@override_settings(ALLOWED_HOSTS=["localhost", "testserver"])
class ColumnsConfirmTests(TestCase):
    def setUp(self):
        F.sync_builtin_fields()
        self.client = verified_client()
        Member.objects.create(first_name="Ana", last_name="Roux", city="Nyon", roles=[Role.COACH], status=MemberStatus.ACTIF)
        self.view = SavedView.objects.create(name="base", columns=["last_name", "first_name", "roles"])

    @staticmethod
    def heads(response):
        html = response.content.decode()
        return re.findall(r"<th>([^<]*)</th>", html[html.index("<thead>"): html.index("</thead>")])

    def test_columns_apply_immediately_even_when_a_saved_view_is_open(self):
        r = self.client.post("/contacts/colonnes/", {"columns": ["last_name", "first_name", "city"], "next": f"/contacts/?view={self.view.pk}"})
        self.assertIn(f"view={self.view.pk}", r.headers["Location"])
        self.assertIn("cols=last_name%2Cfirst_name%2Ccity", r.headers["Location"])
        shown = self.heads(self.client.get(r.headers["Location"]))
        self.assertIn("Ville", shown)
        self.assertNotIn("Rôles", shown)
        # la vue partagée n'a pas été modifiée : rouverte sans choix, elle garde ses colonnes
        self.view.refresh_from_db()
        self.assertEqual(self.view.columns, ["last_name", "first_name", "roles"])
        self.assertIn("Rôles", self.heads(self.client.get(f"/contacts/?view={self.view.pk}")))

    def test_without_a_saved_view_the_choice_is_stored_and_shown(self):
        r = self.client.post("/contacts/colonnes/", {"columns": ["last_name", "city"], "next": "/contacts/?cat=membres"})
        self.assertNotIn("cols=", r.headers["Location"])
        self.assertEqual(self.heads(self.client.get(r.headers["Location"]))[:2], ["Nom", "Ville"])

    def test_duplicate_and_unknown_columns_are_dropped(self):
        self.client.post("/contacts/colonnes/", {"columns": ["city", "city", "inconnue", "last_name", "city"], "next": "/contacts/"})
        self.assertEqual(UserListPreference.objects.get(user__username="comite").columns, ["city", "last_name"])

    def test_foreign_next_address_is_ignored(self):
        r = self.client.post("/contacts/colonnes/", {"columns": ["city"], "next": "https://evil.example/?view=1"})
        self.assertEqual(r.headers["Location"], "/contacts/")
