from datetime import date

from django.test import TestCase

from apps.members import fields as F
from apps.members import services
from apps.members.models import ContactGroup, Member, MemberStatus, Profile


class ServicesTests(TestCase):
    def test_member_id_generation_and_homonyms(self):
        a = Member.objects.create(first_name="Léa", last_name="Dupont")
        b = Member.objects.create(first_name="Lea", last_name="Dupont")
        c = Member.objects.create(first_name="Jean-Édouard", last_name="Müller")
        self.assertEqual(a.member_id, "lea.dupont")
        self.assertEqual(b.member_id, "lea.dupont2")
        self.assertEqual(c.member_id, "jean-edouard.muller")

    def test_age_category_by_season_end_year(self):
        cases = {
            date(2020, 1, 1): "U8",
            date(2018, 6, 1): "U10",
            date(2016, 6, 1): "U12",
            date(2014, 6, 1): "U14",
            date(2011, 6, 1): "U17",
            date(2008, 6, 1): "U20",
            date(1995, 6, 1): "Sénior",
            date(1980, 6, 1): "Vétéran",
        }
        for bd, expected in cases.items():
            self.assertEqual(services.age_category(bd, reference_year=2027), expected, bd)

    def test_trial_profile_has_no_category_and_fixed_status(self):
        m = Member.objects.create(first_name="Tom", last_name="Berger", profile=Profile.ESSAI, birth_date=date(2016, 1, 1), status=MemberStatus.ACTIF)
        self.assertEqual(m.status, MemberStatus.ESSAI)
        self.assertEqual(m.category, "")

    def test_avs_validation_and_format(self):
        self.assertEqual(services.format_avs("7561234567897"), "756.1234.5678.97")
        self.assertTrue(services.avs_is_valid("756.1234.5678.97"))
        self.assertFalse(services.avs_is_valid("756.1234.5678.90"))

    def test_family_discount(self):
        self.assertEqual(services.compute_contribution(550, True), 450)
        self.assertEqual(services.compute_contribution(550, False), 550)
        self.assertIsNone(services.compute_contribution(None, True))

    def test_sensitive_field_never_in_default_columns(self):
        F.sync_builtin_fields()
        self.assertNotIn("avs_number", F.DEFAULT_LIST_COLUMNS)
        avs = [d for d in F.all_field_definitions() if d.key == "avs_number"][0]
        self.assertTrue(avs.is_sensitive)

    def test_category_queries(self):
        g = ContactGroup.objects.create(name="Comité")
        m = Member.objects.create(first_name="A", last_name="B", status=MemberStatus.ACTIF)
        m.groups.add(g)
        Member.objects.create(first_name="C", last_name="D", status=MemberStatus.INACTIF)
        Member.objects.create(first_name="", last_name="", kind="ENTREPRISE", company_name="Sponsor SA", status=MemberStatus.INACTIF)
        self.assertEqual(Member.objects.members().count(), 1)
        self.assertEqual(Member.objects.non_members().count(), 1)
        self.assertEqual(Member.objects.companies().count(), 1)
        self.assertEqual(Member.objects.companies().first().member_id, "sponsor-sa")


from decimal import Decimal  # noqa: E402

from django.contrib.auth.models import User  # noqa: E402
from django.test import Client, override_settings  # noqa: E402
from django_otp import DEVICE_ID_SESSION_KEY  # noqa: E402
from django_otp.plugins.otp_totp.models import TOTPDevice  # noqa: E402

from apps.members.models import TariffBracket, TrainingMode  # noqa: E402


def verified_client(username="comite"):
    """Client de test connecté ET vérifié par A2F (le middleware exige les deux)."""
    user = User.objects.create_user(username, password="x")
    device = TOTPDevice.objects.create(user=user, name="test", confirmed=True)
    client = Client(HTTP_HOST="localhost")
    client.force_login(user)
    session = client.session
    session[DEVICE_ID_SESSION_KEY] = device.persistent_id
    session.save()
    return client


@override_settings(ALLOWED_HOSTS=["localhost", "testserver"])
class ValidateRegistrationTests(TestCase):
    def setUp(self):
        F.sync_builtin_fields()
        self.client = verified_client()
        self.mode = TrainingMode.objects.create(name="2 jours", days_per_week=2)
        self.bracket = TariffBracket.objects.create(name="Dès 20 ans")
        self.member = Member.objects.create(first_name="Sam", last_name="Petit", profile=Profile.MAJEUR, status=MemberStatus.EN_ATTENTE)

    def test_validation_requires_bracket_and_stays_pending(self):
        r = self.client.post(f"/contacts/{self.member.pk}/valider/", {})
        self.assertEqual(r.status_code, 302)
        self.member.refresh_from_db()
        self.assertEqual(self.member.status, MemberStatus.EN_ATTENTE)

    def test_validation_sets_billing_info_and_activates(self):
        self.client.post(
            f"/contacts/{self.member.pk}/valider/",
            {"tariff_bracket": self.bracket.pk, "training_mode": self.mode.pk, "family_discount": "on"},
        )
        self.member.refresh_from_db()
        self.assertEqual(self.member.status, MemberStatus.ACTIF)
        self.assertEqual(self.member.tariff_bracket, self.bracket)
        self.assertEqual(self.member.training_mode, self.mode)
        self.assertTrue(self.member.family_discount)
        self.assertIsNotNone(self.member.entry_date)

    def test_trial_validation_needs_no_billing_info(self):
        trial = Member.objects.create(first_name="Tom", last_name="Essai", profile=Profile.ESSAI, status=MemberStatus.EN_ATTENTE)
        self.client.post(f"/contacts/{trial.pk}/valider/")
        trial.refresh_from_db()
        self.assertEqual(trial.status, MemberStatus.ESSAI)

    def test_detail_page_offers_validation_modal(self):
        r = self.client.get(f"/contacts/{self.member.pk}/")
        self.assertContains(r, 'id="validateModal"')
