import time

from django.core import mail, signing
from django.test import Client, TestCase, override_settings

from apps.formbuilder.models import FormDefinition, FormField
from apps.formbuilder.views import _seed_default_fields
from apps.members import fields as F
from apps.members.models import Member, MemberStatus, Profile, TrainingMode


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", ALLOWED_HOSTS=["testserver"])
class PublicFormTests(TestCase):
    def setUp(self):
        F.sync_builtin_fields()
        TrainingMode.objects.create(name="1 jour", days_per_week=1)
        self.fd = FormDefinition.objects.create(name="Inscription", slug="inscription", profile=Profile.MAJEUR)
        _seed_default_fields(self.fd)
        self.client = Client()

    def name(self, key):
        return self.fd.fields.get(field_definition__key=key).input_name

    def payload(self, **over):
        data = {
            self.fd.fields.get(kind=FormField.Kind.PROFILE).input_name: Profile.MINEUR,
            self.name("first_name"): "Émile", self.name("last_name"): "Zola", self.name("address"): "Rue Neuve 3",
            self.name("postal_code"): "1297", self.name("city"): "Founex", self.name("birth_date"): "2014-05-06",
            self.name("phone_parent1"): "+41 79 111 22 33", self.name("email_parent1"): "zola@example.com",
            self.name("training_days"): ["LUN"], "ts_token": signing.dumps(int(time.time()) - 10), "website_url": "",
        }
        data.update(over)
        return data

    def test_public_page_is_anonymous_and_management_is_not(self):
        self.assertEqual(self.client.get("/formulaires/public/inscription/").status_code, 200)
        self.assertEqual(self.client.get("/contacts/").status_code, 302)
        self.assertEqual(self.client.get("/formulaires/").status_code, 302)

    def test_submission_creates_pending_member_and_notifies(self):
        r = self.client.post("/formulaires/public/inscription/", self.payload())
        self.assertEqual(r.status_code, 200)
        m = Member.objects.get(last_name="Zola")
        self.assertEqual(m.status, MemberStatus.EN_ATTENTE)
        self.assertEqual(m.profile, Profile.MINEUR)
        self.assertEqual(m.email_parent1, "zola@example.com")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Zola", mail.outbox[0].subject)
        self.assertIn("Email parent 1 : zola@example.com", mail.outbox[0].body)

    def test_honeypot_and_speed_checks(self):
        self.client.post("/formulaires/public/inscription/", self.payload(website_url="http://spam"))
        self.client.post("/formulaires/public/inscription/", self.payload(ts_token=signing.dumps(int(time.time()))))
        self.assertFalse(Member.objects.exists())

    def test_conditional_parent_fields_not_required_for_adults(self):
        prof = self.fd.fields.get(kind=FormField.Kind.PROFILE).input_name
        data = self.payload(**{prof: Profile.MAJEUR, self.name("phone_parent1"): "", self.name("email_parent1"): "", self.name("email"): "a@example.com", self.name("birth_date"): "1990-01-01"})
        self.client.post("/formulaires/public/inscription/", data)
        m = Member.objects.get(last_name="Zola")
        self.assertEqual(m.profile, Profile.MAJEUR)

    def test_minor_requires_parent_contact(self):
        data = self.payload(**{self.name("phone_parent1"): "", self.name("email_parent1"): ""})
        self.client.post("/formulaires/public/inscription/", data)
        self.assertFalse(Member.objects.exists())

    def test_committee_only_fields_never_offered(self):
        keys = {ff.field_definition.key for ff in self.fd.fields.all() if ff.field_definition}
        self.assertFalse(keys & {"status", "tariff_bracket", "family_discount", "role", "notes"})
