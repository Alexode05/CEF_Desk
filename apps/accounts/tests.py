import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from apps.accounts.models import AccountProfile

User = get_user_model()
PASSWORD = "Un-mot-de-passe-solide-42"


def extract_link(body):
    match = re.search(r"https?://\S+", body)
    assert match, body
    return match.group(0).replace("http://testserver", "")


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CEF_REGISTRATION_CODE="code-test",
    ALLOWED_HOSTS=["testserver"],
)
class RegistrationAndVerificationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

    def register(self, **over):
        data = {
            "username": "lea", "first_name": "Léa", "last_name": "Comité", "email": "Lea@Example.com",
            "invitation_code": "code-test", "password1": PASSWORD, "password2": PASSWORD,
        }
        data.update(over)
        return self.client.post("/compte/creer-un-compte/", data)

    def test_registration_creates_inactive_account_and_sends_link(self):
        r = self.register()
        self.assertRedirects(r, "/compte/verification/envoyee/")
        user = User.objects.get(username="lea")
        self.assertFalse(user.is_active)
        self.assertEqual(user.email, "lea@example.com")
        self.assertFalse(AccountProfile.for_user(user).email_verified)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["lea@example.com"])
        self.assertIn("/compte/verification/", mail.outbox[0].body)
        # pas connecté automatiquement, et la page d'accueil reste fermée
        self.assertRedirects(self.client.get("/"), "/compte/connexion/?next=/")

    def test_wrong_invitation_code_and_duplicate_email_are_refused(self):
        self.register(invitation_code="faux")
        self.assertFalse(User.objects.exists())
        User.objects.create_user("autre", email="lea@example.com", password=PASSWORD)
        self.register()
        self.assertFalse(User.objects.filter(username="lea").exists())

    def test_unverified_account_cannot_log_in_and_sees_resend_link(self):
        self.register()
        r = self.client.post("/compte/connexion/", {"username": "lea", "password": PASSWORD})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "pas encore vérifiée")
        self.assertContains(r, "/compte/verification/renvoyer/")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_verification_link_activates_once_then_login_with_password(self):
        self.register()
        link = extract_link(mail.outbox[0].body)
        r = self.client.get(link)
        self.assertRedirects(r, "/compte/connexion/")
        user = User.objects.get(username="lea")
        self.assertTrue(user.is_active)
        self.assertTrue(AccountProfile.for_user(user).email_verified)
        # le lien ne resservira pas à autre chose qu'à dire « déjà vérifié »
        self.assertRedirects(self.client.get(link), "/compte/connexion/")
        r = self.client.post("/compte/connexion/", {"username": "lea", "password": PASSWORD})
        self.assertRedirects(r, "/")
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_tampered_link_is_rejected(self):
        self.register()
        link = extract_link(mail.outbox[0].body)
        r = self.client.get(link[:-3] + "abc/")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(User.objects.get(username="lea").is_active)

    def test_resend_sends_a_new_link_without_revealing_accounts(self):
        self.register()
        mail.outbox.clear()
        r = self.client.post("/compte/verification/renvoyer/", {"email": "LEA@example.com"})
        self.assertRedirects(r, "/compte/verification/envoyee/")
        self.assertEqual(len(mail.outbox), 1)
        r = self.client.post("/compte/verification/renvoyer/", {"email": "inconnu@example.com"})
        self.assertRedirects(r, "/compte/verification/envoyee/")  # même réponse, aucun email
        self.assertEqual(len(mail.outbox), 1)

    def test_dev_link_is_never_shown_outside_debug(self):
        self.register()
        page = self.client.get("/compte/verification/envoyee/")
        self.assertNotContains(page, "Mode développement")

    @override_settings(DEBUG=True, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_dev_link_is_shown_in_local_development(self):
        self.register()
        page = self.client.get("/compte/verification/envoyee/")
        self.assertContains(page, "Mode développement")
        self.assertContains(page, "/compte/verification/")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", ALLOWED_HOSTS=["testserver"])
class PasswordLoginTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.user = User.objects.create_user("marc", email="marc@example.com", password=PASSWORD)

    def test_login_with_username_or_email(self):
        self.assertRedirects(self.client.post("/compte/connexion/", {"username": "marc", "password": PASSWORD}), "/")
        self.client.logout()
        self.assertRedirects(self.client.post("/compte/connexion/", {"username": "MARC@example.com", "password": PASSWORD}), "/")

    def test_no_two_factor_step_any_more(self):
        self.client.post("/compte/connexion/", {"username": "marc", "password": PASSWORD})
        self.assertEqual(self.client.get("/contacts/").status_code, 200)
        self.assertEqual(self.client.get("/compte/a2f/verification/").status_code, 404)

    def test_wrong_password(self):
        r = self.client.post("/compte/connexion/", {"username": "marc", "password": "faux"})
        self.assertContains(r, "Identifiant ou mot de passe incorrect")

    def test_lockout_after_five_failures_even_with_the_right_password(self):
        for _ in range(5):
            self.client.post("/compte/connexion/", {"username": "marc", "password": "faux"})
        r = self.client.post("/compte/connexion/", {"username": "marc", "password": PASSWORD})
        self.assertContains(r, "Trop de tentatives")
        self.assertNotIn("_auth_user_id", self.client.session)
        cache.clear()  # fin du blocage
        self.assertRedirects(self.client.post("/compte/connexion/", {"username": "marc", "password": PASSWORD}), "/")

    def test_deactivated_account_gets_a_clear_message(self):
        AccountProfile.for_user(self.user).mark_verified()
        self.user.is_active = False
        self.user.save()
        r = self.client.post("/compte/connexion/", {"username": "marc", "password": PASSWORD})
        self.assertContains(r, "Ce compte est désactivé")

    def test_password_reset_flow(self):
        r = self.client.post("/compte/mot-de-passe-oublie/", {"email": "marc@example.com"})
        self.assertRedirects(r, "/compte/mot-de-passe-oublie/envoye/")
        self.assertEqual(len(mail.outbox), 1)
        link = extract_link(mail.outbox[0].body)
        r = self.client.get(link)  # Django redirige vers l'URL « set-password »
        r = self.client.post(r.headers["Location"], {"new_password1": "Nouveau-mot-de-passe-99", "new_password2": "Nouveau-mot-de-passe-99"})
        self.assertRedirects(r, "/compte/mot-de-passe-oublie/termine/")
        self.assertRedirects(self.client.post("/compte/connexion/", {"username": "marc", "password": "Nouveau-mot-de-passe-99"}), "/")

    def test_password_reset_for_unknown_email_sends_nothing(self):
        r = self.client.post("/compte/mot-de-passe-oublie/", {"email": "inconnu@example.com"})
        self.assertRedirects(r, "/compte/mot-de-passe-oublie/envoye/")
        self.assertEqual(len(mail.outbox), 0)


@override_settings(ALLOWED_HOSTS=["testserver"])
class AccessControlTests(TestCase):
    def test_management_pages_admin_and_media_require_login(self):
        client = Client()
        for path in ("/", "/contacts/", "/comptabilite/", "/parametres/", "/admin/"):
            r = client.get(path)
            self.assertEqual(r.status_code, 302, path)
            self.assertTrue(r.headers["Location"].startswith("/compte/connexion/?next="), path)
        # Fichiers téléversés (factures, documents) : jamais publics. Hors mode DEBUG ils ne sont pas
        # servis du tout (404) ; en DEBUG ils passent par le middleware (redirection vers la connexion).
        from django.conf import settings

        from apps.accounts.middleware import PUBLIC_PATH_PREFIXES

        self.assertNotIn("/" + settings.MEDIA_URL.lstrip("/"), PUBLIC_PATH_PREFIXES)
        self.assertIn(client.get("/media/factures/2026/x.pdf").status_code, (302, 404))

    def test_public_pages_stay_open(self):
        client = Client()
        for path in ("/compte/connexion/", "/compte/mot-de-passe-oublie/", "/compte/verification/renvoyer/"):
            self.assertEqual(client.get(path).status_code, 200, path)
        self.assertEqual(client.get("/formulaires/public/inexistant/").status_code, 404)  # public : 404 et non redirection

    def test_superuser_reaches_admin_after_login(self):
        User.objects.create_superuser("admin-test", email="a@example.com", password=PASSWORD)
        client = Client()
        client.post("/compte/connexion/", {"username": "admin-test", "password": PASSWORD})
        self.assertEqual(client.get("/admin/").status_code, 200)
