from unittest.mock import patch

import pyotp
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from google.auth import exceptions as google_exceptions
from rest_framework.test import APIClient

from .models import TOTPDevice

User = get_user_model()
CLIENT_ID = "test-client.apps.googleusercontent.com"


@override_settings(GOOGLE_OAUTH_CLIENT_ID=CLIENT_ID)
class GoogleSignInTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "Pine-forest!47-trail"
        cls.user = User.objects.create_user("student@sdu.edu.kz", cls.password)

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.claims = {"sub": "google-123", "email": "New.Person@gmail.com", "email_verified": True}
        verifier = patch("accounts.google.id_token.verify_oauth2_token", side_effect=self.verify)
        self.verify_mock = verifier.start()
        self.addCleanup(verifier.stop)
        self.prepare()

    def verify(self, credential, request, audience, **kwargs):
        if credential != "valid-token" or audience != CLIENT_ID:
            raise ValueError("Invalid token")
        return {**self.claims, "nonce": self.nonce}

    def prepare(self):
        body = self.client.get(reverse("google-sign-in")).json()
        self.token, self.nonce = body["csrf_token"], body["nonce"]

    def google(self, credential="valid-token", name="google-sign-in", method="post"):
        payload = {"credential": credential} if credential is not None else {}
        return getattr(self.client, method)(
            reverse(name), payload, format="json", HTTP_X_CSRFTOKEN=self.token,
        )

    def test_get_returns_client_id_and_session_nonce(self):
        body = self.client.get(reverse("google-sign-in")).json()
        self.assertEqual(set(body), {"client_id", "nonce", "csrf_token"})
        self.assertEqual(body["client_id"], CLIENT_ID)
        self.assertEqual(body["nonce"], self.nonce)
        self.assertGreaterEqual(len(self.nonce), 32)

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="")
    def test_disabled_without_client_id(self):
        body = self.client.get(reverse("google-sign-in")).json()
        self.assertIsNone(body["client_id"])
        self.assertEqual(self.google().status_code, 404)

    def test_first_google_sign_in_creates_passwordless_account(self):
        response = self.google()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {"email", "csrf_token"})
        user = User.objects.get(google_subject="google-123")
        self.assertEqual(user.email, "new.person@gmail.com")
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.profile_type, User.ProfileType.VISITOR)
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))

    def test_returning_user_is_matched_by_subject_not_email(self):
        User.objects.filter(pk=self.user.pk).update(google_subject="google-123")
        self.claims["email"] = "renamed@gmail.com"
        self.assertEqual(self.google().json()["email"], self.user.email)
        self.assertEqual(User.objects.count(), 1)

    def test_existing_email_is_never_joined_automatically(self):
        self.claims["email"] = "STUDENT@sdu.edu.kz"
        response = self.google()
        self.assertEqual(response.status_code, 409)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.google_subject)

    def test_rejects_forged_unverified_or_foreign_tokens(self):
        for credential in ("forged", "", 42, None):
            with self.subTest(credential=credential):
                self.assertEqual(self.google(credential).status_code, 400)
        self.claims["email_verified"] = False
        self.assertEqual(self.google().status_code, 400)
        self.assertFalse(User.objects.filter(google_subject="google-123").exists())

    def test_rejects_token_minted_for_another_session(self):
        original = self.nonce
        other = APIClient(enforce_csrf_checks=True)
        other.get(reverse("google-sign-in"))
        self.nonce = "nonce-from-somewhere-else"
        self.assertEqual(self.google().status_code, 400)
        self.nonce = original
        self.assertEqual(self.google().status_code, 200)

    def test_requires_csrf(self):
        response = self.client.post(reverse("google-sign-in"), {"credential": "valid-token"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.verify_mock.assert_not_called()

    def test_google_outage_is_503(self):
        self.verify_mock.side_effect = google_exceptions.TransportError("down")
        self.assertEqual(self.google().status_code, 503)

    def test_inactive_account_is_refused(self):
        User.objects.filter(pk=self.user.pk).update(google_subject="google-123", is_active=False)
        self.assertEqual(self.google().status_code, 401)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_google_sign_in_still_requires_second_factor(self):
        secret = pyotp.random_base32()
        User.objects.filter(pk=self.user.pk).update(google_subject="google-123")
        TOTPDevice.objects.create(user=self.user, secret=secret, confirmed=True)
        response = self.google()
        self.assertEqual(set(response.json()), {"two_factor_required", "csrf_token"})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.token = response.json()["csrf_token"]
        verified = self.client.post(
            reverse("two-factor-verify"), {"code": pyotp.TOTP(secret).now()},
            format="json", HTTP_X_CSRFTOKEN=self.token,
        )
        self.assertEqual(verified.status_code, 200)

    # Linking from the profile

    def sign_in_with_password(self):
        token = self.client.get(reverse("login")).json()["csrf_token"]
        response = self.client.post(reverse("login"), {
            "email": self.user.email, "password": self.password,
        }, format="json", HTTP_X_CSRFTOKEN=token)
        self.token = response.json()["csrf_token"]
        self.prepare()

    def test_link_requires_session(self):
        self.assertEqual(self.google(name="google-link").status_code, 401)

    def test_link_then_sign_in_with_google_then_unlink(self):
        self.sign_in_with_password()
        linked = self.google(name="google-link")
        self.assertEqual(linked.status_code, 200)
        self.assertTrue(linked.json()["google_linked"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.google_subject, "google-123")

        self.client.post(reverse("logout"), HTTP_X_CSRFTOKEN=self.token)
        self.client = APIClient(enforce_csrf_checks=True)
        self.prepare()
        self.assertEqual(self.google().json()["email"], self.user.email)

        self.token = self.client.get(reverse("security")).json()["csrf_token"]
        unlinked = self.google(credential=None, name="google-link", method="delete")
        self.assertEqual(unlinked.status_code, 200)
        self.assertFalse(unlinked.json()["google_linked"])

    def test_cannot_link_google_account_owned_by_someone_else(self):
        User.objects.create_user("owner@gmail.com", None, google_subject="google-123")
        self.sign_in_with_password()
        self.assertEqual(self.google(name="google-link").status_code, 409)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.google_subject)

    def test_passwordless_account_cannot_unlink_its_only_sign_in(self):
        self.assertEqual(self.google().status_code, 200)
        self.token = self.client.get(reverse("security")).json()["csrf_token"]
        response = self.google(credential=None, name="google-link", method="delete")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(User.objects.filter(google_subject="google-123").exists())
