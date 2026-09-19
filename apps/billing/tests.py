from datetime import date, timedelta
from decimal import Decimal

from django.core import mail
from django.test import TestCase, override_settings
from stdnum import iso11649
from stdnum.ch import esr

from apps.billing import services
from apps.billing.management.commands.check_qrbill import spec_checks
from apps.billing.models import Invoice, InvoiceStatus, Tariff
from apps.billing.pdf import build_qrbill, split_street
from apps.dashboard.models import ClubSettings
from apps.members.models import Member, MemberStatus, TariffBracket, TrainingMode


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class BillingTests(TestCase):
    def setUp(self):
        self.club = ClubSettings.load()
        self.club.treasurer_email = "tresorier@example.invalid"
        self.club.save()
        self.mode = TrainingMode.objects.create(name="2 jours", days_per_week=2)
        self.bracket = TariffBracket.objects.create(name="Moins de 20 ans")
        Tariff.objects.create(training_mode=self.mode, bracket=self.bracket, amount=Decimal("550.00"))
        self.member = Member.objects.create(
            first_name="Noah", last_name="Dupont", address="Chemin des Vignes 4", postal_code="1297", city="Founex",
            email_parent1="parents@example.com", training_mode=self.mode, tariff_bracket=self.bracket,
            family_discount=True, status=MemberStatus.ACTIF,
        )

    def test_split_street(self):
        self.assertEqual(split_street("Chemin des Vignes 4"), ("Chemin des Vignes", "4"))
        self.assertEqual(split_street("Route Suisse 12b"), ("Route Suisse", "12b"))
        self.assertEqual(split_street("Case postale"), ("Case postale", None))

    def test_qr_reference_and_scor_reference(self):
        ref = services.make_reference(self.club, 22, 2027)
        self.assertEqual(len(ref), 27)
        self.assertTrue(esr.is_valid(ref))
        classic = type("C", (), {"is_qr_iban": False})()
        scor = services.make_reference(classic, 12, 2027)
        self.assertTrue(scor.startswith("RF"))
        self.assertTrue(iso11649.is_valid(scor))

    def test_invoice_creation_pdf_and_payload(self):
        inv = services.create_invoice_for_member(self.member)
        self.assertEqual(inv.amount, Decimal("450.00"))
        self.assertEqual(inv.family_discount, Decimal("100.00"))
        self.assertTrue(inv.number.startswith(f"{self.club.season_reference_year()}-"))
        self.assertTrue(inv.pdf.name.endswith(".pdf"))
        self.assertIsNotNone(inv.archived_file)
        self.assertEqual(inv.archived_file.folder.path, f"Club/Factures/{inv.season}")
        payload = build_qrbill(self.club, inv).qr_data()
        self.assertEqual(spec_checks(payload), [])
        with self.assertRaises(services.BillingError):
            services.create_invoice_for_member(self.member)  # doublon même saison

    def test_missing_tariff_blocks_invoice(self):
        self.member.tariff_bracket = None
        self.member.save()
        with self.assertRaises(services.BillingError):
            services.create_invoice_for_member(self.member)

    def test_send_with_treasurer_cc_then_reminder_then_paid(self):
        inv = services.create_invoice_for_member(self.member)
        services.send_invoice_email(inv)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["parents@example.com"])
        self.assertEqual(mail.outbox[0].cc, ["tresorier@example.invalid"])
        self.assertEqual(len(mail.outbox[0].attachments), 1)
        inv.refresh_from_db()
        self.assertEqual(inv.status, InvoiceStatus.ENVOYEE)
        self.assertEqual(inv.next_reminder_date, inv.issue_date + timedelta(days=self.club.reminder_delay_days))
        self.assertFalse(inv.reminder_is_due)

        inv.issue_date = date.today() - timedelta(days=40)
        inv.save()
        sent, errors = services.run_due_reminders()
        self.assertEqual([i.pk for i in sent], [inv.pk])
        inv.refresh_from_db()
        self.assertEqual(inv.status, InvoiceStatus.RELANCEE)
        self.assertEqual(inv.reminder_count, 1)

        services.mark_paid(inv)
        self.assertEqual(inv.status, InvoiceStatus.PAYEE)
        self.assertIsNone(inv.next_reminder_date)
        self.assertEqual(Invoice.objects.unpaid().count(), 0)


from apps.members.tests import verified_client  # noqa: E402


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", ALLOWED_HOSTS=["localhost", "testserver"])
class ManualInvoiceTests(TestCase):
    def setUp(self):
        self.club = ClubSettings.load()
        self.club.treasurer_email = "tresorier@example.invalid"
        self.club.save()
        self.sponsor = Member.objects.create(
            kind="ENTREPRISE", company_name="Sponsor SA", first_name="", last_name="", address="Rue du Lac 5",
            postal_code="1260", city="Nyon", email="compta@sponsor.example",
        )

    def test_manual_invoice_pdf_qr_and_archive(self):
        inv = services.create_manual_invoice(self.sponsor, Decimal("1250.50"), "  Stage de Pâques\n2027 ")
        self.assertEqual(inv.kind, "MANUELLE")
        self.assertTrue(inv.is_manual)
        self.assertEqual(inv.amount, Decimal("1250.50"))
        self.assertEqual(inv.description, "Stage de Pâques 2027")
        self.assertEqual(inv.debtor_name, "Sponsor SA")
        self.assertEqual(inv.recipient_email, "compta@sponsor.example")
        self.assertIsNotNone(inv.archived_file)
        payload = build_qrbill(self.club, inv).qr_data()
        self.assertEqual(spec_checks(payload), [])
        self.assertIn("Stage de Pâques 2027", payload)
        # plusieurs factures manuelles pour le même contact et la même saison : autorisé
        second = services.create_manual_invoice(self.sponsor, Decimal("80"), "Location de salle")
        self.assertNotEqual(inv.number, second.number)
        self.assertNotEqual(inv.reference, second.reference)

    def test_manual_invoice_validation(self):
        with self.assertRaises(services.BillingError):
            services.create_manual_invoice(self.sponsor, Decimal("0"), "x")
        with self.assertRaises(services.BillingError):
            services.create_manual_invoice(self.sponsor, Decimal("10"), "   ")
        with self.assertRaises(services.BillingError):
            services.create_manual_invoice(self.sponsor, Decimal("10"), "x", issue_date=date(2026, 9, 10), due_date=date(2026, 9, 1))

    def test_manual_invoice_email_uses_generic_text_and_treasurer_cc(self):
        inv = services.create_manual_invoice(self.sponsor, Decimal("300"), "Stage de Pâques")
        services.send_invoice_email(inv)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ["compta@sponsor.example"])
        self.assertEqual(msg.cc, ["tresorier@example.invalid"])
        self.assertIn("Stage de Pâques", msg.subject)
        self.assertIn("Sponsor SA", msg.subject)
        self.assertIn(f"facture n° {inv.number} concernant Stage de Pâques", msg.body)
        self.assertNotIn("cotisation", msg.body.lower())

    def test_cotisation_email_still_mentions_the_membership(self):
        mode = TrainingMode.objects.create(name="2 jours", days_per_week=2)
        bracket = TariffBracket.objects.create(name="Dès 20 ans")
        Tariff.objects.create(training_mode=mode, bracket=bracket, amount=Decimal("500"))
        member = Member.objects.create(first_name="Marc", last_name="Favre", address="Rue du Lac 12", postal_code="1260", city="Nyon",
                                       email="marc@example.com", training_mode=mode, tariff_bracket=bracket, status=MemberStatus.ACTIF)
        services.send_invoice_email(services.create_invoice_for_member(member))
        msg = mail.outbox[0]
        self.assertIn("Cotisation", msg.subject)
        self.assertIn("la cotisation de la saison", msg.body)
        self.assertIn("Marc Favre", msg.body)

    def test_manual_invoice_through_the_page(self):
        client = verified_client()
        self.assertEqual(client.get("/comptabilite/factures/manuelle/").status_code, 200)
        page = client.get(f"/comptabilite/factures/manuelle/?member={self.sponsor.pk}")
        self.assertContains(page, "Sponsor SA")
        r = client.post("/comptabilite/factures/manuelle/", {
            "member": self.sponsor.pk, "amount": "450.00", "description": "Publicité",
            "issue_date": "2026-09-20", "due_date": "2026-10-20", "recipient_email": "",
        })
        self.assertEqual(r.status_code, 302)
        inv = Invoice.objects.get(kind="MANUELLE")
        self.assertEqual(r.headers["Location"], f"/comptabilite/factures/{inv.pk}/")
        self.assertEqual(client.get(r.headers["Location"]).status_code, 200)
        self.assertEqual(client.get(f"/comptabilite/factures/{inv.pk}/pdf/").status_code, 200)
        # refus d'un montant négatif
        bad = client.post("/comptabilite/factures/manuelle/", {
            "member": self.sponsor.pk, "amount": "-5", "description": "x", "issue_date": "2026-09-20", "due_date": "2026-10-20",
        })
        self.assertEqual(bad.status_code, 200)
        self.assertEqual(Invoice.objects.filter(kind="MANUELLE").count(), 1)
