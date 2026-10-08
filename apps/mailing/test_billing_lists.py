"""Listes de diffusion automatiques « à facturer » : ajout à la validation, sortie dès l'envoi de la facture."""
from datetime import date
from decimal import Decimal

from django.core import mail
from django.test import TestCase, override_settings

from apps.billing import services
from apps.billing.models import Invoice, InvoiceStatus, Tariff
from apps.dashboard.models import ClubSettings
from apps.mailing.billing_lists import ensure_billing_lists
from apps.mailing.models import MailingList
from apps.members import fields as F
from apps.members.models import Member, MemberStatus, Profile, TariffBracket, TrainingMode
from apps.members.tests import verified_client


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", ALLOWED_HOSTS=["localhost", "testserver"])
class BillingListsTests(TestCase):
    def setUp(self):
        F.sync_builtin_fields()
        ensure_billing_lists()
        self.membership = MailingList.objects.get(kind=MailingList.Kind.BILLING, billing_rule=MailingList.BillingRule.MEMBERSHIP)
        self.trials = MailingList.objects.get(kind=MailingList.Kind.BILLING, billing_rule=MailingList.BillingRule.TRIAL)
        self.mode = TrainingMode.objects.create(name="2 jours", days_per_week=2)
        self.bracket = TariffBracket.objects.create(name="Dès 20 ans")
        Tariff.objects.create(training_mode=self.mode, bracket=self.bracket, amount=Decimal("500.00"))
        self.client = verified_client()
        self.season = ClubSettings.load().current_season_label()

    def pending(self, profile, **over):
        data = dict(first_name="Sam", last_name="Petit", profile=profile, status=MemberStatus.EN_ATTENTE, address="Rue 1",
                    postal_code="1297", city="Founex", email="sam@example.com", training_mode=self.mode)
        data.update(over)
        return Member.objects.create(**data)

    def names(self, ml):
        return [m.display_name for m in ml.members()]

    # --- création des listes ----------------------------------------------------------
    def test_the_two_system_lists_exist_once(self):
        ensure_billing_lists()  # idempotent
        self.assertEqual(MailingList.objects.filter(kind=MailingList.Kind.BILLING).count(), 2)
        self.assertEqual(self.membership.name, "Inscriptions définitives à facturer")
        self.assertEqual(self.trials.name, "Cours d'essai à facturer")

    # --- ajout automatique à la validation --------------------------------------------
    def test_validated_registration_is_added_automatically(self):
        member = self.pending(Profile.MAJEUR)
        self.assertEqual(self.names(self.membership), [])  # en attente : pas encore dans la liste
        r = self.client.post(f"/contacts/{member.pk}/valider/", {"tariff_bracket": self.bracket.pk, "training_mode": self.mode.pk})
        self.assertEqual(self.names(self.membership), ["Sam Petit"])
        self.assertEqual(self.names(self.trials), [])
        self.assertIn("Inscriptions définitives à facturer", str(list(r.wsgi_request._messages)[0]))

    def test_validated_trial_goes_to_the_trial_list(self):
        trial = self.pending(Profile.ESSAI, first_name="Tom", last_name="Essai", training_mode=None)
        self.client.post(f"/contacts/{trial.pk}/valider/")
        self.assertEqual(self.names(self.trials), ["Tom Essai"])
        self.assertEqual(self.names(self.membership), [])

    def test_not_validated_inactive_licence_only_and_companies_are_not_listed(self):
        self.pending(Profile.MAJEUR, first_name="A")
        self.pending(Profile.MAJEUR, first_name="B", status=MemberStatus.INACTIF)
        self.pending(Profile.MAJEUR, first_name="C", status=MemberStatus.LICENCE)
        Member.objects.create(kind="ENTREPRISE", company_name="Sponsor SA", first_name="", last_name="", status=MemberStatus.ACTIF, profile=Profile.MAJEUR)
        self.pending(Profile.ESSAI, first_name="D")  # essai pas encore validé
        self.assertEqual(self.names(self.membership), [])
        self.assertEqual(self.names(self.trials), [])

    # --- sortie dès l'envoi -----------------------------------------------------------
    def test_member_leaves_the_list_once_the_invoice_is_sent(self):
        member = self.pending(Profile.MAJEUR, status=MemberStatus.ACTIF, tariff_bracket=self.bracket)
        invoice = services.create_invoice_for_member(member)
        self.assertEqual(self.names(self.membership), ["Sam Petit"])  # générée seulement : reste dans la liste
        services.send_invoice_email(invoice)
        self.assertEqual(self.names(self.membership), [])
        for status in (InvoiceStatus.RELANCEE, InvoiceStatus.PAYEE):
            invoice.status = status
            invoice.save()
            self.assertEqual(self.names(self.membership), [], status)
        invoice.status = InvoiceStatus.ANNULEE  # facture annulée : il faut refacturer, il revient
        invoice.save()
        self.assertEqual(self.names(self.membership), ["Sam Petit"])

    def test_paid_without_email_also_leaves_the_list(self):
        member = self.pending(Profile.MAJEUR, status=MemberStatus.ACTIF, tariff_bracket=self.bracket)
        services.mark_paid(services.create_invoice_for_member(member))
        self.assertEqual(self.names(self.membership), [])

    def test_previous_season_or_manual_invoices_do_not_remove_the_member(self):
        member = self.pending(Profile.MAJEUR, status=MemberStatus.ACTIF, tariff_bracket=self.bracket)
        Invoice.objects.create(number="2019-0001", kind="COTISATION", member=member, season="2018-2019", base_amount=1, amount=1,
                               description="x", debtor_name="x", issue_date=date(2018, 10, 1), due_date=date(2018, 11, 1), status=InvoiceStatus.PAYEE)
        manual = services.create_manual_invoice(member, Decimal("30"), "Stage")
        services.send_invoice_email(manual)
        self.assertEqual(self.names(self.membership), ["Sam Petit"])  # la cotisation de la saison n'est pas envoyée

    def test_trial_leaves_once_its_trial_invoice_is_sent(self):
        trial = self.pending(Profile.ESSAI, first_name="Tom", last_name="Essai", status=MemberStatus.ESSAI, training_mode=None)
        invoice = services.create_invoice_for_member(trial)
        self.assertEqual(self.names(self.trials), ["Tom Essai"])
        services.send_invoice_email(invoice)
        self.assertEqual(self.names(self.trials), [])

    # --- parcours complet par les pages -----------------------------------------------
    def test_full_flow_validate_generate_send_from_the_lists(self):
        adult = self.pending(Profile.MAJEUR)
        minor = self.pending(Profile.MINEUR, first_name="Lia", email="", email_parent1="parent1@example.com")
        trial = self.pending(Profile.ESSAI, first_name="Tom", last_name="Essai", training_mode=None)
        for m in (adult, minor):
            self.client.post(f"/contacts/{m.pk}/valider/", {"tariff_bracket": self.bracket.pk, "training_mode": self.mode.pk})
        self.client.post(f"/contacts/{trial.pk}/valider/")

        for ml, expected_amounts in ((self.membership, ["500.00", "500.00"]), (self.trials, ["50.00"])):
            page = self.client.get(f"/comptabilite/lots/nouveau/?list={ml.pk}")
            self.assertEqual(page.status_code, 200)
            r = self.client.post("/comptabilite/lots/nouveau/", {"label": f"Lot {ml.pk}", "mailing_list": ml.pk, "only_active": "on",
                                                                    "skip_already_invoiced": "on", "confirm": "1"})
            batch_url = r.headers["Location"]
            invoices = list(Invoice.objects.filter(batch__label=f"Lot {ml.pk}"))
            self.assertEqual(sorted(str(i.amount) for i in invoices), expected_amounts)
            self.assertEqual(len(ml.members()), len(expected_amounts))  # générées, pas encore envoyées
            self.client.post(f"{batch_url}envoyer/", {"ids": [i.pk for i in invoices]})
            self.assertEqual(list(ml.members()), [])  # envoyées : la liste se vide

        self.assertIn(["parent1@example.com"], [m.to for m in mail.outbox])  # la facture du mineur est partie au parent 1
        self.assertEqual(len(mail.outbox), 3)

    def test_trial_list_prefills_a_trial_batch_label(self):
        page = self.client.get(f"/comptabilite/lots/nouveau/?list={self.trials.pk}")
        self.assertContains(page, "Cours d&#x27;essai" if "&#x27;" in page.content.decode() else "Cours d'essai")

    # --- protection des listes système -------------------------------------------------
    def test_system_lists_cannot_be_deleted_edited_or_created(self):
        r = self.client.post(f"/mailing/listes/{self.membership.pk}/supprimer/")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(MailingList.objects.filter(pk=self.membership.pk).exists())
        index = self.client.get("/mailing/")
        self.assertNotContains(index, f"/mailing/listes/{self.membership.pk}/supprimer/")
        self.assertContains(index, "Inscriptions définitives à facturer")
        detail = self.client.get(f"/mailing/listes/{self.membership.pk}/")
        self.assertContains(detail, "Liste automatique")
        self.assertNotContains(detail, f"/mailing/listes/{self.membership.pk}/supprimer/")
        r = self.client.post("/mailing/listes/nouvelle/", {"name": "Fausse", "kind": "BILLING"})
        self.assertEqual(r.status_code, 200)  # type refusé par le formulaire
        self.assertFalse(MailingList.objects.filter(name="Fausse").exists())
