from django.test import TestCase, override_settings

from apps.mailing.models import MailingList
from apps.members.tests import verified_client


@override_settings(ALLOWED_HOSTS=["localhost", "testserver"])
class MailingListDeleteTests(TestCase):
    def test_list_can_be_deleted_from_index_and_detail(self):
        client = verified_client()
        ml = MailingList.objects.create(name="A supprimer", kind=MailingList.Kind.STATIC)
        page = client.get("/mailing/")
        self.assertContains(page, f"/mailing/listes/{ml.pk}/supprimer/")
        client.post(f"/mailing/listes/{ml.pk}/supprimer/")
        self.assertFalse(MailingList.objects.filter(pk=ml.pk).exists())


@override_settings(ALLOWED_HOSTS=["localhost", "testserver"])
class ListFromSelectionTests(TestCase):
    def setUp(self):
        from apps.members.models import Member

        self.client = verified_client()
        self.a = Member.objects.create(first_name="Ana", last_name="A", email="ana@example.com")
        self.b = Member.objects.create(first_name="Ben", last_name="B", email_parent1="parents@example.com")
        self.c = Member.objects.create(first_name="Cy", last_name="C")  # sans email

    def test_selection_becomes_a_static_list(self):
        ids = f"{self.a.pk},{self.b.pk},{self.c.pk}"
        r = self.client.post("/mailing/listes/depuis-selection/", {"ids": ids, "name": "Stage Pâques", "description": "Inscrits", "next": "/contacts/"})
        ml = MailingList.objects.get(name="Stage Pâques")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers["Location"], f"/mailing/listes/{ml.pk}/")
        self.assertEqual(ml.kind, MailingList.Kind.STATIC)
        self.assertEqual(sorted(m.pk for m in ml.members()), sorted([self.a.pk, self.b.pk, self.c.pk]))
        self.assertEqual(len(ml.recipients()), 2)  # le contact sans email n'est pas destinataire
        page = self.client.get(r.headers["Location"])
        self.assertContains(page, "Stage Pâques")

    def test_refuses_empty_selection_duplicate_name_and_foreign_redirect(self):
        self.assertEqual(self.client.post("/mailing/listes/depuis-selection/", {"ids": "", "name": "X"}).status_code, 302)
        self.assertFalse(MailingList.objects.exists())
        MailingList.objects.create(name="Déjà là", kind=MailingList.Kind.STATIC)
        self.client.post("/mailing/listes/depuis-selection/", {"ids": str(self.a.pk), "name": "déjà là"})
        self.assertEqual(MailingList.objects.count(), 1)
        r = self.client.post("/mailing/listes/depuis-selection/", {"ids": "", "name": "X", "next": "https://evil.example/"})
        self.assertEqual(r.headers["Location"], "/contacts/")  # jamais de redirection hors du site

    def test_contacts_page_offers_the_button_and_modal(self):
        page = self.client.get("/contacts/")
        self.assertContains(page, "Créer une liste de diffusion")
        self.assertContains(page, "/mailing/listes/depuis-selection/")
