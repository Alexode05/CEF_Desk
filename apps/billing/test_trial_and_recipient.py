"""Destinataire des factures (parent 1 pour un mineur) et facturation du cours d'essai (montant fixe)."""
from decimal import Decimal

from django.core import mail
from django.test import TestCase, override_settings

from apps.billing import services
from apps.billing.forms import BatchCreateForm
from apps.billing.management.commands.check_qrbill import spec_checks
from apps.billing.models import Invoice, InvoiceStatus, Tariff
from apps.billing.pdf import build_qrbill
from apps.dashboard.models import ClubSettings
from apps.members.models import ContactGroup, Member, MemberStatus, Profile, TariffBracket, TrainingMode
from apps.members.tests import verified_client


def tariffed_member(**over):
    """Membre facturable (modalité + tranche + tarif de 550 CHF) ; profil mineur par défaut."""
    mode, _ = TrainingMode.objects.get_or_create(name="2 jours", defaults={"days_per_week": 2})
    bracket, _ = TariffBracket.objects.get_or_create(name="Moins de 20 ans")
    Tariff.objects.update_or_create(training_mode=mode, bracket=bracket, defaults={"amount": Decimal("550.00")})
    data = dict(
        first_name="Noah", last_name="Dupont", profile=Profile.MINEUR, status=MemberStatus.ACTIF, address="Chemin des Vignes 4",
        postal_code="1297", city="Founex", training_mode=mode, tariff_bracket=bracket,
    )
    data.update(over)
    return Member.objects.create(**data)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class InvoiceRecipientTests(TestCase):
    def setUp(self):
        self.club = ClubSettings.load()
        self.club.treasurer_email = "tresorier@example.invalid"
        self.club.save()

    def test_minor_invoice_goes_to_parent_1_not_to_the_child(self):
        m = tariffed_member(email="eleve@example.com", email_parent1="parent1@example.com", email_parent2="parent2@example.com")
        inv = services.create_invoice_for_member(m)
        self.assertEqual(inv.recipient_email, "parent1@example.com")
        services.send_invoice_email(inv)
        self.assertEqual(mail.outbox[0].to, ["parent1@example.com"])
        self.assertEqual(mail.outbox[0].cc, ["tresorier@example.invalid"])
        self.assertNotIn("eleve@example.com", mail.outbox[0].to + mail.outbox[0].cc)

    def test_minor_fallbacks_when_parent_1_is_missing(self):
        m = tariffed_member(email="eleve@example.com", email_parent2="parent2@example.com")
        self.assertEqual(m.primary_email, "parent2@example.com")
        m.email_parent2 = ""
        self.assertEqual(m.primary_email, "eleve@example.com")

    def test_adult_keeps_their_own_address(self):
        m = tariffed_member(profile=Profile.MAJEUR, email="adulte@example.com", email_parent1="ancien@example.com")
        self.assertEqual(m.primary_email, "adulte@example.com")

    def test_corrected_address_is_used_even_after_the_invoice_was_generated(self):
        m = tariffed_member(email_parent1="ancienne@example.com")
        inv = services.create_invoice_for_member(m)
        m.email_parent1 = "nouvelle@example.com"
        m.save()
        inv.refresh_from_db()
        self.assertEqual(inv.display_recipient, "nouvelle@example.com")  # affiché dans le lot avant l'envoi
        services.send_invoice_email(inv)
        self.assertEqual(mail.outbox[0].to, ["nouvelle@example.com"])
        inv.refresh_from_db()
        self.assertEqual(inv.recipient_email, "nouvelle@example.com")

    def test_reminder_goes_to_parent_1_too(self):
        m = tariffed_member(email="eleve@example.com", email_parent1="parent1@example.com")
        inv = services.create_invoice_for_member(m)
        services.send_invoice_email(inv)
        services.send_invoice_email(inv, reminder=True)
        self.assertEqual([msg.to for msg in mail.outbox], [["parent1@example.com"], ["parent1@example.com"]])

    def test_manual_invoice_explicit_address_wins_otherwise_parent_1(self):
        m = tariffed_member(email="eleve@example.com", email_parent1="parent1@example.com")
        explicit = services.create_manual_invoice(m, Decimal("40"), "Stage", recipient_email="comptabilite@example.com")
        default = services.create_manual_invoice(m, Decimal("40"), "Stage 2")
        self.assertEqual(explicit.resolve_recipient(), "comptabilite@example.com")
        self.assertEqual(default.resolve_recipient(), "parent1@example.com")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", ALLOWED_HOSTS=["localhost", "testserver"])
class TrialInvoiceTests(TestCase):
    def setUp(self):
        self.club = ClubSettings.load()
        self.club.treasurer_email = "tresorier@example.invalid"
        self.club.save()
        self.trial = Member.objects.create(
            first_name="Tom", last_name="Berger", profile=Profile.ESSAI, status=MemberStatus.ESSAI, address="Route Suisse 8",
            postal_code="1290", city="Versoix", email="famille.berger@example.com",
        )

    def test_trial_course_is_a_fixed_50_chf(self):
        self.assertEqual(self.club.trial_fee, Decimal("50.00"))
        self.assertEqual(self.trial.computed_amount, Decimal("50.00"))
        inv = services.create_invoice_for_member(self.trial)
        self.assertEqual((inv.kind, inv.amount, inv.base_amount, inv.family_discount), ("ESSAI", Decimal("50.00"), Decimal("50.00"), Decimal("0.00")))
        self.assertEqual(inv.description, "Cours d'essai - Tom Berger")
        self.assertEqual(inv.training_mode_label, "")
        self.assertTrue(inv.is_trial and not inv.is_cotisation and not inv.is_manual)
        self.assertIsNotNone(inv.archived_file)
        payload = build_qrbill(self.club, inv).qr_data()
        self.assertEqual(spec_checks(payload), [])
        self.assertIn("50.00", payload)
        self.assertIn("Cours d'essai - Tom Berger", payload)

    def test_trial_ignores_the_tariff_grid_and_family_discount(self):
        self.trial.family_discount = True
        self.trial.save()
        self.assertEqual(services.create_invoice_for_member(self.trial).amount, Decimal("50.00"))

    def test_trial_fee_is_read_from_club_settings(self):
        self.club.trial_fee = Decimal("65.00")
        self.club.save()
        self.assertEqual(services.create_invoice_for_member(self.trial).amount, Decimal("65.00"))

    def test_trial_can_only_be_billed_once_unless_cancelled(self):
        inv = services.create_invoice_for_member(self.trial)
        with self.assertRaises(services.BillingError):
            services.create_invoice_for_member(self.trial)
        inv.status = InvoiceStatus.ANNULEE
        inv.save()
        self.assertEqual(services.create_invoice_for_member(self.trial).amount, Decimal("50.00"))

    def test_trial_email_wording_and_recipient(self):
        inv = services.create_invoice_for_member(self.trial)
        services.send_invoice_email(inv)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ["famille.berger@example.com"])
        self.assertEqual(msg.cc, ["tresorier@example.invalid"])
        self.assertIn("Cours d'essai", msg.subject)
        self.assertIn("le cours d'essai de Tom Berger", msg.body)
        self.assertNotIn("cotisation", msg.body.lower())

    def test_trial_status_shows_in_the_contact_list_column(self):
        inv = services.create_invoice_for_member(self.trial)
        self.assertEqual(Member.objects.prefetch_related("invoices").get(pk=self.trial.pk).invoice_status_label, "Générée (non envoyée)")
        services.mark_paid(inv)
        self.assertEqual(Member.objects.prefetch_related("invoices").get(pk=self.trial.pk).invoice_status_label, "Payée")

    def test_batch_generation_includes_trial_members(self):
        group = ContactGroup.objects.create(name="Essais-test")
        group.members.add(self.trial)
        form = BatchCreateForm({"label": "Essais", "group": group.pk, "only_active": "on", "skip_already_invoiced": "on"})
        self.assertTrue(form.is_valid(), form.errors)
        members = list(form.members())
        self.assertEqual(members, [self.trial])
        batch, created, errors = services.create_batch(members, "Essais")
        self.assertEqual([(i.kind, i.amount) for i in created], [("ESSAI", Decimal("50.00"))])
        self.assertEqual(errors, [])

    def test_manual_invoice_does_not_block_the_cotisation_nor_the_batch(self):
        member = tariffed_member(email_parent1="p@example.com")
        services.create_manual_invoice(member, Decimal("120"), "Stage de Pâques")
        cotisation = services.create_invoice_for_member(member)  # n'est plus refusée à cause de la facture manuelle
        self.assertEqual(cotisation.kind, "COTISATION")
        member2 = tariffed_member(first_name="Lia", last_name="Autre", email_parent1="q@example.com")
        services.create_manual_invoice(member2, Decimal("10"), "Stage")
        r = verified_client().post(
            "/comptabilite/lots/nouveau/",
            {"label": "x", "ids": str(member2.pk), "only_active": "on", "skip_already_invoiced": "on", "confirm": "1"},
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Invoice.objects.filter(member=member2, kind="COTISATION").count(), 1)

    def test_pages_for_a_trial_member(self):
        client = verified_client()
        detail = client.get(f"/contacts/{self.trial.pk}/")
        self.assertContains(detail, "CHF 50,00)")
        self.assertContains(detail, "Facturer le cours d")
        page = client.get(f"/comptabilite/factures/nouvelle/{self.trial.pk}/")
        self.assertContains(page, "montant fixe")
        self.assertContains(page, "50,00")
        r = client.post(f"/comptabilite/factures/nouvelle/{self.trial.pk}/")
        inv = Invoice.objects.get(member=self.trial)
        self.assertEqual(r.headers["Location"], f"/comptabilite/factures/{inv.pk}/")
        self.assertEqual(client.get(r.headers["Location"]).status_code, 200)
        self.assertEqual(client.get(f"/comptabilite/factures/{inv.pk}/pdf/").status_code, 200)
        self.assertEqual(client.get("/comptabilite/factures/?etat=toutes").status_code, 200)
        self.assertEqual(client.get(f"/comptabilite/lots/{services.create_batch([], 'vide')[0].pk}/").status_code, 200)
