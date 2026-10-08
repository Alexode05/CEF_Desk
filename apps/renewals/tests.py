"""Passage à la saison suivante : invitation, formulaire personnel, validation, démission."""
import re
from datetime import date, timedelta
from decimal import Decimal

from django.core import mail
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from apps.billing import services as billing
from apps.billing.models import Invoice, InvoiceStatus, Tariff
from apps.dashboard.models import ClubSettings
from apps.members import fields as F
from apps.members.models import ContactGroup, Member, MemberStatus, Profile, Role, TariffBracket, TrainingMode
from apps.members.tests import verified_client
from apps.renewals.forms import DEFAULT_BODY, DEFAULT_SUBJECT
from apps.renewals.models import RenewalRequest, SeasonRollover

Status = RenewalRequest.Status


def link_in(body):
    return re.search(r"https?://\S+/saison-suivante/verifier/\S+/", body).group(0).replace("http://localhost", "")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", ALLOWED_HOSTS=["localhost", "testserver"])
class SeasonRolloverTests(TestCase):
    def setUp(self):
        F.sync_builtin_fields()
        club = ClubSettings.load()
        club.secretariat_email = "secretariat@example.com"
        club.save()
        self.mode1 = TrainingMode.objects.create(name="1 jour", days_per_week=1)
        self.mode2 = TrainingMode.objects.create(name="2 jours", days_per_week=2)
        self.bracket = TariffBracket.objects.create(name="Moins de 20 ans")
        self.bracket2 = TariffBracket.objects.create(name="Dès 20 ans")
        Tariff.objects.create(training_mode=self.mode1, bracket=self.bracket, amount=Decimal("400"))
        self.lundi = ContactGroup.objects.create(name="Lundi", is_course=True, public_choice=True)
        self.mardi = ContactGroup.objects.create(name="Mardi", is_course=True, public_choice=True)
        self.comite = ContactGroup.objects.create(name="Comité", public_choice=False)
        self.minor = Member.objects.create(
            first_name="Léa", last_name="Dupont", profile=Profile.MINEUR, status=MemberStatus.ACTIF, address="Chemin des Vignes 4",
            postal_code="1297", city="Founex", email="lea@example.com", email_parent1="parent1@example.com",
            avs_number="756.1234.5678.97", training_mode=self.mode1, tariff_bracket=self.bracket, roles=[Role.TIREUR],
            notes="Note interne", licence_number="CH-1",
        )
        self.minor.groups.add(self.lundi, self.comite)
        self.adult = Member.objects.create(first_name="Marc", last_name="Favre", profile=Profile.MAJEUR, status=MemberStatus.ACTIF,
                                           address="Rue du Lac 12", postal_code="1260", city="Nyon", email="marc@example.com")
        self.no_email = Member.objects.create(first_name="Sans", last_name="Email", profile=Profile.MAJEUR, status=MemberStatus.ACTIF)
        Member.objects.create(first_name="En", last_name="Attente", status=MemberStatus.EN_ATTENTE, email="x@example.com")
        Member.objects.create(first_name="Ex", last_name="Membre", status=MemberStatus.INACTIF, email="y@example.com")
        Member.objects.create(first_name="Tom", last_name="Essai", profile=Profile.ESSAI, status=MemberStatus.ESSAI, email="z@example.com")
        self.client = verified_client()
        self.season = "2099-2100"

    def launch(self, members=None, **over):
        members = members if members is not None else [self.minor, self.adult, self.no_email]
        data = {"target_season": self.season, "subject": DEFAULT_SUBJECT, "body": DEFAULT_BODY, "members": [m.pk for m in members]}
        data.update(over)
        from apps.renewals import services

        with self.settings():  # la saison proposée dépend de la date : on la force pour le test
            orig = services.season_choices
            services.season_choices = lambda: [(self.season, self.season)]
            try:
                return self.client.post("/saison-suivante/", data)
            finally:
                services.season_choices = orig

    def public_link(self, member):
        msg = next(m for m in mail.outbox if member.first_name in m.subject)
        return link_in(msg.body)

    # --- lancement --------------------------------------------------------------------------------
    def test_dashboard_has_the_button_and_launch_page_lists_active_members_only(self):
        self.assertContains(self.client.get("/"), "Passage à la saison suivante")
        page = self.client.get("/saison-suivante/")
        self.assertEqual(page.status_code, 200)
        for name in ("Léa Dupont", "Marc Favre", "Sans Email"):
            self.assertContains(page, name)
        for name in ("En Attente", "Ex Membre", "Tom Essai"):
            self.assertNotContains(page, name)
        self.assertContains(page, "parent1@example.com")  # adresse de facturation d'un mineur
        self.assertContains(page, "aucune adresse")

    def test_launch_sends_personal_links_to_the_billing_address(self):
        r = self.launch()
        rollover = SeasonRollover.objects.get(target_season=self.season)
        self.assertRedirects(r, f"/saison-suivante/{rollover.pk}/", fetch_redirect_response=False)
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["marc@example.com", "parent1@example.com"])
        self.assertEqual(rollover.requests.get(member=self.no_email).status, Status.FAILED)
        bodies = [m.body for m in mail.outbox]
        self.assertTrue(all("/saison-suivante/verifier/" in b for b in bodies))
        self.assertNotEqual(link_in(bodies[0]), link_in(bodies[1]))  # un lien différent par membre
        req = rollover.requests.get(member=self.minor)
        self.assertNotIn(link_in(mail.outbox[0].body).split("/")[-2], req.token_hash)  # seul le hachage est stocké

    def test_body_without_link_is_refused_and_second_launch_only_invites_new_members(self):
        self.launch(body="Pas de lien ici")
        self.assertFalse(SeasonRollover.objects.exists())
        self.launch([self.minor])
        self.launch([self.minor, self.adult])
        self.assertEqual([m.to[0] for m in mail.outbox], ["parent1@example.com", "marc@example.com"])
        self.assertEqual(SeasonRollover.objects.count(), 1)

    # --- formulaire public ------------------------------------------------------------------------
    def test_public_form_shows_current_data_but_never_committee_or_sensitive_values(self):
        self.launch([self.minor])
        anon = Client()
        page = anon.get(self.public_link(self.minor))
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        for value in ("Chemin des Vignes 4", "Founex", "parent1@example.com", "lea@example.com"):
            self.assertIn(value, html)
        self.assertNotIn("756.1234.5678.97", html)  # AVS jamais en clair
        self.assertIn("756.****.****.97", html)
        for hidden in ("Note interne", "CH-1", "Tranche tarifaire", "Rôles", "Statut", "Comité"):
            self.assertNotIn(hidden, html)
        self.assertIn("Démission", html)

    def test_invalid_and_expired_links(self):
        anon = Client()
        self.assertEqual(anon.get("/saison-suivante/verifier/inexistant/").status_code, 404)
        self.launch([self.minor])
        link = self.public_link(self.minor)
        RenewalRequest.objects.update(expires_at=timezone.now() - timedelta(days=1))
        self.assertContains(anon.get(link), "Lien expiré", status_code=410)

    def test_confirming_with_changes_creates_a_request_to_validate_without_touching_the_fiche(self):
        self.launch([self.minor])
        anon = Client()
        link = self.public_link(self.minor)
        page = anon.get(link).content.decode()
        data = self._form_data_from(page)
        data.update({"action": "confirm", "city": "Coppet", "postal_code": "1296", "training_mode": str(self.mode2.pk),
                     "groups": [str(self.mardi.pk)], "avs_number": "", "remark": "Nouvelle adresse"})
        r = anon.post(link, data)
        self.assertContains(r, "Merci")
        req = RenewalRequest.objects.get(member=self.minor)
        self.assertEqual(req.status, Status.TO_VALIDATE)
        self.assertEqual(sorted(c["key"] for c in req.changes), ["city", "groups", "postal_code", "training_mode"])
        self.minor.refresh_from_db()
        self.assertEqual(self.minor.city, "Founex")  # rien n'est appliqué avant la validation du comité
        notification = mail.outbox[-1]
        self.assertEqual(notification.to, ["secretariat@example.com"])
        self.assertIn("Ville : Founex → Coppet", notification.body)
        self.assertIn("Nouvelle adresse", notification.body)
        # le lien ne sert qu'une fois
        self.assertContains(anon.get(link), "Réponse déjà reçue", status_code=410)
        # la réponse apparaît sur le tableau de bord, comme une inscription à traiter
        self.assertContains(self.client.get("/"), "Passage de saison : réponses à traiter")

    def test_new_avs_is_validated_and_never_sent_in_clear_by_email(self):
        self.launch([self.minor])
        anon = Client()
        link = self.public_link(self.minor)
        data = self._form_data_from(anon.get(link).content.decode())
        data.update({"action": "confirm", "avs_number": "756.0000.0000.00"})
        self.assertContains(anon.post(link, data), "AVS invalide")
        data["avs_number"] = "7569217076985"
        anon.post(link, data)
        req = RenewalRequest.objects.get(member=self.minor)
        self.assertEqual([c["key"] for c in req.changes], ["avs_number"])
        self.assertNotIn("756.9217.0769.85", mail.outbox[-1].body)

    def test_validation_applies_changes_and_billing_info_keeping_internal_groups(self):
        self.launch([self.minor])
        anon = Client()
        link = self.public_link(self.minor)
        data = self._form_data_from(anon.get(link).content.decode())
        data.update({"action": "confirm", "city": "Coppet", "groups": [str(self.mardi.pk)], "training_mode": str(self.mode2.pk)})
        anon.post(link, data)
        req = RenewalRequest.objects.get(member=self.minor)
        self.minor.refresh_from_db()
        self.minor.notes = "Modifiée par le comité entre-temps"
        self.minor.save()
        review = self.client.get(f"/saison-suivante/reponse/{req.pk}/")
        self.assertContains(review, "Coppet")
        r = self.client.post(f"/saison-suivante/reponse/{req.pk}/", {"action": "validate", "training_mode": self.mode2.pk,
                                                                         "tariff_bracket": self.bracket2.pk, "family_discount": "on"})
        self.assertEqual(r.status_code, 302)
        self.minor.refresh_from_db()
        req.refresh_from_db()
        self.assertEqual(req.status, Status.VALIDATED)
        self.assertEqual((self.minor.city, self.minor.training_mode, self.minor.tariff_bracket, self.minor.family_discount),
                         ("Coppet", self.mode2, self.bracket2, True))
        self.assertEqual(sorted(g.name for g in self.minor.groups.all()), ["Comité", "Mardi"])  # « Comité » conservé
        self.assertEqual(self.minor.notes, "Modifiée par le comité entre-temps")  # champs non modifiés intacts
        self.assertEqual(self.minor.status, MemberStatus.ACTIF)

    def test_confirming_without_changes(self):
        self.launch([self.adult])
        anon = Client()
        link = self.public_link(self.adult)
        data = self._form_data_from(anon.get(link).content.decode())
        data["action"] = "confirm"
        anon.post(link, data)
        req = RenewalRequest.objects.get(member=self.adult)
        self.assertEqual((req.status, req.changes), (Status.TO_VALIDATE, []))
        self.assertIn("Aucune modification", mail.outbox[-1].body)

    # --- démission --------------------------------------------------------------------------------
    def test_resignation_requires_confirmation_then_committee_deletes_the_fiche_keeping_invoices(self):
        invoice = billing.create_invoice_for_member(self.minor)
        self.launch([self.minor])
        anon = Client()
        link = self.public_link(self.minor)
        anon.post(link, {"action": "resign", "resign_remark": "Déménagement"})  # case non cochée
        self.assertEqual(RenewalRequest.objects.get(member=self.minor).status, Status.SENT)
        r = anon.post(link, {"action": "resign", "resign_remark": "Déménagement", "confirm_resign": "on"})
        self.assertContains(r, "Démission transmise")
        req = RenewalRequest.objects.get(member=self.minor)
        self.assertEqual(req.status, Status.RESIGNATION)
        self.assertIn("démission annoncée", mail.outbox[-1].subject)
        self.assertTrue(Member.objects.filter(pk=self.minor.pk).exists())  # rien n'est supprimé sans le comité

        # facture impayée : suppression refusée
        r = self.client.post(f"/saison-suivante/reponse/{req.pk}/", {"action": "confirm_resignation", "confirm": self.minor.member_id})
        self.assertTrue(Member.objects.filter(pk=self.minor.pk).exists())
        billing.mark_paid(invoice)
        # mauvaise confirmation : refusée
        self.client.post(f"/saison-suivante/reponse/{req.pk}/", {"action": "confirm_resignation", "confirm": "faux"})
        self.assertTrue(Member.objects.filter(pk=self.minor.pk).exists())
        # confirmation correcte : fiche supprimée, facture conservée
        self.client.post(f"/saison-suivante/reponse/{req.pk}/", {"action": "confirm_resignation", "confirm": self.minor.member_id})
        self.assertFalse(Member.objects.filter(pk=self.minor.pk).exists())
        invoice.refresh_from_db()
        self.assertIsNone(invoice.member)
        self.assertEqual(invoice.debtor_label, "Léa Dupont")
        req.refresh_from_db()
        self.assertEqual((req.status, req.member_name), (Status.RESIGNED, "Léa Dupont"))
        # les pages de facturation fonctionnent toujours avec une facture sans fiche
        for path in ("/comptabilite/factures/?etat=toutes", f"/comptabilite/factures/{invoice.pk}/", "/comptabilite/", "/"):
            self.assertEqual(self.client.get(path).status_code, 200, path)
        self.assertEqual(self.client.post(f"/comptabilite/factures/{invoice.pk}/regenerer/").status_code, 302)
        self.assertEqual(self.client.get(f"/saison-suivante/{req.rollover_id}/").status_code, 200)

    def test_committee_can_keep_the_fiche(self):
        self.launch([self.adult])
        anon = Client()
        anon.post(self.public_link(self.adult), {"action": "resign", "confirm_resign": "on"})
        req = RenewalRequest.objects.get(member=self.adult)
        self.client.post(f"/saison-suivante/reponse/{req.pk}/", {"action": "keep"})
        req.refresh_from_db()
        self.assertEqual(req.status, Status.KEPT)
        self.assertTrue(Member.objects.filter(pk=self.adult.pk).exists())

    # --- relance ----------------------------------------------------------------------------------
    def test_resend_invalidates_the_previous_link(self):
        self.launch([self.adult])
        old_link = self.public_link(self.adult)
        req = RenewalRequest.objects.get(member=self.adult)
        self.client.post(f"/saison-suivante/invitation/{req.pk}/renvoyer/")
        new_link = link_in(mail.outbox[-1].body)
        self.assertNotEqual(old_link, new_link)
        anon = Client()
        self.assertEqual(anon.get(old_link).status_code, 404)
        self.assertEqual(anon.get(new_link).status_code, 200)

    # --- suppression manuelle d'une fiche : factures conservées ----------------------------------
    def test_member_delete_page_keeps_paid_invoices_and_blocks_unpaid(self):
        invoice = billing.create_invoice_for_member(self.minor)
        self.client.post(f"/contacts/{self.minor.pk}/supprimer/", {"confirm": self.minor.member_id})
        self.assertTrue(Member.objects.filter(pk=self.minor.pk).exists())
        billing.mark_paid(invoice)
        self.client.post(f"/contacts/{self.minor.pk}/supprimer/", {"confirm": self.minor.member_id})
        self.assertFalse(Member.objects.filter(pk=self.minor.pk).exists())
        self.assertTrue(Invoice.objects.filter(pk=invoice.pk, member__isnull=True, status=InvoiceStatus.PAYEE).exists())

    # --- outil ------------------------------------------------------------------------------------
    @staticmethod
    def _form_data_from(html):
        """Reproduit l'envoi du formulaire tel qu'affiché (valeurs pré-remplies)."""
        data = {}
        form_html = html[html.index('value="confirm"'):html.index("</form>", html.index('value="confirm"'))]
        for name, value in re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', form_html):
            if name in ("csrfmiddlewaretoken", "action"):
                continue
            if re.search(rf'name="{re.escape(name)}"[^>]*type="checkbox"|type="checkbox"[^>]*name="{re.escape(name)}"', form_html):
                continue
            data[name] = value.replace("&#x27;", "'").replace("&amp;", "&")
        for name, value in re.findall(r'<input[^>]*type="checkbox"[^>]*name="([^"]+)"[^>]*value="([^"]*)"[^>]*checked', form_html):
            data.setdefault(name, []).append(value)
        for name, value in re.findall(r'<input[^>]*type="date"[^>]*name="([^"]+)"[^>]*value="([^"]*)"', form_html):
            data[name] = value
        for name, body in re.findall(r'<select name="([^"]+)"[^>]*>(.*?)</select>', form_html, re.S):
            selected = re.search(r'<option value="([^"]*)"[^>]*selected', body)
            data[name] = selected.group(1) if selected else ""
        return data
