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


from django.http import QueryDict  # noqa: E402

from apps.members import filters as FL  # noqa: E402
from apps.members import layout  # noqa: E402
from apps.members.forms import MemberForm  # noqa: E402
from apps.members.models import FieldDefinition, Role  # noqa: E402


def layout_post(profile, definitions, **overrides):
    """Simule le formulaire de l'éditeur : ordre = ordre de la liste, tout est affiché sauf indication contraire."""
    q = QueryDict(mutable=True)
    for d in definitions:
        q.appendlist("ids", str(d.pk))
        q[f"label_{d.pk}"] = overrides.get(f"label_{d.key}", d.label_for(profile))
        q[f"section_{d.pk}"] = overrides.get(f"section_{d.key}", d.section_for(profile))
        if d.key not in overrides.get("hide", []) and d.applies_to(profile):
            q[f"show_{d.pk}"] = "on"
        if d.is_sensitive:
            q[f"sens_{d.pk}"] = "on"
    return q


class ModelEditorTests(TestCase):
    def setUp(self):
        F.sync_builtin_fields()

    def test_phone_label_and_role_dropdown(self):
        self.assertEqual(FieldDefinition.objects.get(key="phone").label, "Téléphone escrimeur.euse")
        form = MemberForm(profile=Profile.MAJEUR)
        self.assertEqual(form.fields["phone"].label, "Téléphone escrimeur.euse")
        self.assertEqual([c[0] for c in form.fields["role"].choices][1:], [r.value for r in Role])
        self.assertEqual(dict(Role.choices)["MAITRE_ARMES"], "Maître d'arme")
        self.assertEqual(MemberForm(profile=Profile.MINEUR).fields["email"].label, "Email élève")
        self.assertEqual(MemberForm(profile=Profile.MAJEUR).fields["email"].label, "Email")

    def test_role_displays_its_label(self):
        m = Member.objects.create(first_name="A", last_name="B", role=Role.TRESORIER)
        self.assertEqual(F.display_value(m, "role"), "Trésorier-ère")

    def test_layout_changes_are_per_profile(self):
        defs = F.all_field_definitions(include_inactive=True)
        defs.sort(key=lambda d: d.order_for(Profile.MAJEUR))
        layout.save_layout(Profile.MAJEUR, layout_post(Profile.MAJEUR, defs, label_city="Localité", hide=["licence_number"], section_role="contact"))
        majeur = MemberForm(profile=Profile.MAJEUR)
        self.assertEqual(majeur.fields["city"].label, "Localité")
        self.assertNotIn("licence_number", majeur.fields)
        self.assertEqual(MemberForm(profile=Profile.MINEUR).fields["city"].label, "Ville")  # Mineur inchangé
        self.assertIn("licence_number", MemberForm(profile=Profile.MINEUR).fields)
        contact = dict((title, [bf.name for bf in fields]) for title, fields in majeur.sections())["Contact"]
        self.assertIn("role", contact)

    def test_order_is_saved_per_profile(self):
        defs = F.all_field_definitions(include_inactive=True)
        defs.sort(key=lambda d: d.order_for(Profile.ESSAI))
        by_key = {d.key: d for d in defs}
        defs.remove(by_key["city"])
        defs.insert(defs.index(by_key["first_name"]), by_key["city"])  # ville avant prénom
        layout.save_layout(Profile.ESSAI, layout_post(Profile.ESSAI, defs))
        names = list(MemberForm(profile=Profile.ESSAI).fields)
        self.assertLess(names.index("city"), names.index("first_name"))

    def test_locked_fields_cannot_be_hidden_and_avs_stays_sensitive(self):
        defs = F.all_field_definitions(include_inactive=True)
        layout.save_layout(Profile.MAJEUR, layout_post(Profile.MAJEUR, defs, hide=["first_name", "last_name", "status"]))
        fields = MemberForm(profile=Profile.MAJEUR).fields
        for key in ("first_name", "last_name", "status"):
            self.assertIn(key, fields)
        post = layout_post(Profile.MAJEUR, defs)
        post.pop(f"sens_{FieldDefinition.objects.get(key='avs_number').pk}", None)
        layout.save_layout(Profile.MAJEUR, post)
        self.assertTrue(FieldDefinition.objects.get(key="avs_number").is_sensitive)

    def test_reset_restores_original_model(self):
        defs = F.all_field_definitions(include_inactive=True)
        layout.save_layout(Profile.MINEUR, layout_post(Profile.MINEUR, defs, label_city="Localité", hide=["licence_number"]))
        layout.reset_layout(Profile.MINEUR)
        form = MemberForm(profile=Profile.MINEUR)
        self.assertEqual(form.fields["city"].label, "Ville")
        self.assertIn("licence_number", form.fields)
        self.assertEqual(form.fields["email"].label, "Email élève")

    def test_choice_filters_accept_labels(self):
        Member.objects.create(first_name="A", last_name="B", status=MemberStatus.LICENCE, sex="F", role=Role.COACH)
        Member.objects.create(first_name="C", last_name="D", status=MemberStatus.ACTIF, sex="M")
        for raw, expected in (("status:eq:Licence uniquement", "A"), ("sex:eq:Féminin", "A"), ("role:eq:Coach", "A"), ("status:eq:ACTIF", "C")):
            qs, rest = FL.apply_db_filters(Member.objects.all(), FL.parse_filters([raw]))
            self.assertEqual([m.first_name for m in qs], [expected], raw)
            self.assertEqual(rest, [])


@override_settings(ALLOWED_HOSTS=["localhost", "testserver"])
class ModelEditorPageTests(TestCase):
    def test_editor_page_and_save_through_http(self):
        F.sync_builtin_fields()
        client = verified_client()
        for profile in Profile.values:
            self.assertEqual(client.get(f"/contacts/champs/?profile={profile}").status_code, 200)
        defs = F.all_field_definitions(include_inactive=True)
        defs.sort(key=lambda d: d.order_for(Profile.MAJEUR))
        data = layout_post(Profile.MAJEUR, defs, label_address="Rue et numéro")
        data["profile"] = Profile.MAJEUR
        data["action"] = "save_layout"
        r = client.post("/contacts/champs/", {k: data.getlist(k) for k in data})  # toutes les valeurs (ids multiples)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(MemberForm(profile=Profile.MAJEUR).fields["address"].label, "Rue et numéro")
        page = client.get("/contacts/nouveau/?profile=MAJEUR")
        self.assertContains(page, "Rue et numéro")
