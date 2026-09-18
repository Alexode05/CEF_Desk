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
