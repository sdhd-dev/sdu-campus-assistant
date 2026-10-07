import logging
import re
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from . import two_factor
from .models import RecoveryCode
from .test_university import Capture

User = get_user_model()


class SecondStepTests(TestCase):
    """The pending sign-in, recovery codes, and their lockout. Email codes themselves are
    covered in test_email_two_factor."""

    @classmethod
    def setUpTestData(cls):
        cls.password = "Pine-forest!47-trail"
        cls.user = User.objects.create_user("student@sdu.edu.kz", cls.password)

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.now = timezone.now()
        for target in ("accounts.email_codes.timezone.now", "accounts.two_factor.timezone.now"):
            clock = patch(target, side_effect=lambda: self.now)
            clock.start()
            self.addCleanup(clock.stop)
        # Every value that must never reach a log line; checked after each test.
        self.secrets = {self.user.email, self.password, "student@"}
        self.capture = Capture()
        logs = patch.object(logging.getLogger("accounts"), "handlers", [self.capture])
        logs.start()
        self.addCleanup(logs.stop)
        self.addCleanup(self.assertLogsHideSecrets)

    def assertLogsHideSecrets(self):
        codes = {c for message in mail.outbox for c in re.findall(r"\b\d{6}\b", message.body)}
        for message in self.capture.messages:
            for secret in (*self.secrets, *codes):
                self.assertNotIn(secret, message)

    def events(self):
        return [message.split()[0] for message in self.capture.messages]

    def post(self, name, payload=None, client=None, token=None):
        return (client or self.client).post(
            reverse(name), payload or {}, format="json", HTTP_X_CSRFTOKEN=token or self.token,
        )

    def verify(self, method, code, client=None):
        return self.post("two-factor-verify", {"method": method, "code": code}, client)

    def password_login(self, client=None):
        client = client or self.client
        self.token = client.get(reverse("login")).json()["csrf_token"]
        response = self.post("login", {"email": self.user.email, "password": self.password}, client)
        self.token = response.json().get("csrf_token", self.token)
        return response

    def enable(self):
        """Turns email codes on directly and returns the recovery codes."""
        User.objects.filter(pk=self.user.pk).update(email_two_factor=True)
        codes = two_factor._issue_recovery_codes(self.user)
        self.secrets.update(codes)
        self.secrets.update(code.replace("-", "") for code in codes)
        return codes

    def last_code(self):
        return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)

    # Sign-in

    def test_password_login_without_2fa_is_unchanged(self):
        response = self.password_login()
        self.assertEqual(set(response.json()), {"email", "csrf_token"})

    def test_password_login_with_2fa_holds_session_until_code(self):
        self.enable()
        response = self.password_login()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {
            "two_factor_required", "methods", "email_hint", "email_code_sent", "resend_in", "csrf_token",
        })
        self.assertEqual(response.json()["methods"], ["email", "recovery"])
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(self.client.get(reverse("current-user")).status_code, 401)
        self.assertEqual(self.client.get(reverse("profile")).status_code, 401)

        verified = self.verify("email", self.last_code())
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(set(verified.json()), {"email", "csrf_token"})
        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))
        self.assertEqual(self.client.get(reverse("current-user")).status_code, 200)

    def test_authenticator_method_no_longer_exists(self):
        self.enable()
        self.password_login()
        self.assertEqual(self.verify("totp", "123456").status_code, 400)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_verify_without_pending_sign_in_is_refused(self):
        codes = self.enable()
        self.token = self.client.get(reverse("login")).json()["csrf_token"]
        response = self.verify("recovery", codes[0])
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_pending_sign_in_expires(self):
        codes = self.enable()
        self.password_login()
        session = self.client.session
        session["two_factor_pending"]["expires"] -= 601
        session.save()
        response = self.verify("recovery", codes[0])
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_inactive_user_cannot_finish_pending_sign_in(self):
        codes = self.enable()
        self.password_login()
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self.verify("recovery", codes[0]).status_code, 401)
        self.assertNotIn("_auth_user_id", self.client.session)

    # Recovery codes

    def test_recovery_code_works_once_in_any_format(self):
        codes = self.enable()
        self.password_login()
        response = self.verify("recovery", f"  {codes[0].upper().replace('-', ' ')} ")
        self.assertEqual(response.status_code, 200)
        self.token = response.json()["csrf_token"]
        self.post("logout")
        self.client = APIClient(enforce_csrf_checks=True)
        self.password_login()
        self.assertEqual(self.verify("recovery", codes[0]).status_code, 400)
        self.assertEqual(self.verify("recovery", codes[1]).status_code, 200)
        self.assertEqual(self.client.get(reverse("security")).json()["recovery_codes_remaining"], 8)

    def test_recovery_codes_are_stored_as_digests(self):
        codes = self.enable()
        stored = list(RecoveryCode.objects.filter(user=self.user).values_list("code_hash", flat=True))
        self.assertEqual(len(stored), 10)
        for code in codes:
            self.assertNotIn(code, stored)
            self.assertNotIn(code.replace("-", ""), stored)

    def test_repeated_wrong_recovery_codes_lock_them(self):
        codes = self.enable()
        self.password_login()
        for _ in range(5):
            self.assertEqual(self.verify("recovery", "aaaaa-aaaaa").status_code, 400)
        # Even a right code is refused during the lockout, from any new sign-in.
        self.password_login()
        self.assertEqual(self.verify("recovery", codes[0]).status_code, 429)
        self.now += timedelta(minutes=6)
        self.assertEqual(self.verify("recovery", codes[0]).status_code, 200)

    def test_security_state_reports_only_safe_fields(self):
        self.password_login()
        body = self.client.get(reverse("security")).json()
        self.assertEqual(set(body), {
            "google_available", "google_linked", "has_password", "two_factor_enabled",
            "email_two_factor_enabled", "recovery_codes_remaining", "email",
            "email_code_pending", "email_resend_in", "csrf_token",
        })
        self.assertTrue(body["has_password"])

    def test_authenticator_endpoints_are_gone(self):
        self.password_login()
        for path in ("setup", "enable", "disable"):
            with self.subTest(path=path):
                response = self.client.post(
                    f"/api/auth/security/two-factor/{path}/", {}, format="json",
                    HTTP_X_CSRFTOKEN=self.token,
                )
                self.assertEqual(response.status_code, 404)

    # Logging

    def test_recovery_and_lockout_events_are_logged_without_codes(self):
        codes = self.enable()
        self.password_login()
        self.verify("recovery", "aaaaa-aaaaa")
        self.verify("recovery", codes[0])
        self.assertEqual(self.events(), ["code_sent", "code_invalid", "recovery_code_used"])
        self.assertIn("purpose=sign_in method=recovery attempts=1", self.capture.messages[1])
        self.assertIn("remaining=9", self.capture.messages[2])

    def test_lockout_is_logged(self):
        self.enable()
        self.password_login()
        for _ in range(6):
            self.verify("recovery", "aaaaa-aaaaa")
        self.assertEqual(self.events()[1:], ["code_invalid"] * 5 + ["locked", "code_refused_locked"])
        self.assertIn("attempts=5", self.capture.messages[5])
