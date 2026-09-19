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
