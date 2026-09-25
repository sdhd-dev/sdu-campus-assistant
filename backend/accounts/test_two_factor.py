import logging
import re
from datetime import timedelta
from unittest.mock import patch

import pyotp
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from .models import RecoveryCode, TOTPDevice
from .test_university import Capture

User = get_user_model()


class TwoFactorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "Pine-forest!47-trail"
        cls.user = User.objects.create_user("student@sdu.edu.kz", cls.password)

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.now = timezone.now()
        clock = patch("accounts.two_factor.timezone.now", side_effect=lambda: self.now)
        clock.start()
        self.addCleanup(clock.stop)
        # Every value that must never reach a log line; checked after each test.
        self.secrets = {self.user.email, self.password}
        self.capture = Capture()
        logs = patch.object(logging.getLogger("accounts"), "handlers", [self.capture])
        logs.start()
        self.addCleanup(logs.stop)
        self.addCleanup(self.assertLogsHideSecrets)

    def assertLogsHideSecrets(self):
        for message in self.capture.messages:
            for secret in self.secrets:
                self.assertNotIn(secret, message)
            self.assertNotIn(self.user.email.split("@")[0], message)

    def events(self):
        return [message.split()[0] for message in self.capture.messages]

    def post(self, name, payload=None, client=None, token=None):
        return (client or self.client).post(
            reverse(name), payload or {}, format="json", HTTP_X_CSRFTOKEN=token or self.token,
        )

    def verify(self, code, client=None):
        """The second sign-in step; the method follows from the code's shape."""
        method = "totp" if re.fullmatch(r"\d{6}", code.strip()) else "recovery"
        return self.post("two-factor-verify", {"method": method, "code": code}, client)

    def password_login(self, client=None):
        client = client or self.client
        self.token = client.get(reverse("login")).json()["csrf_token"]
        response = self.post("login", {"email": self.user.email, "password": self.password}, client)
        self.token = response.json().get("csrf_token", self.token)
        return response

    def code(self, secret, offset=0):
        code = pyotp.TOTP(secret).at(self.now + timedelta(seconds=offset))
        self.secrets.add(code)
        return code

    def enable(self):
        """Signs in, turns 2FA on, signs out. Returns (secret, recovery codes)."""
        self.assertEqual(self.password_login().status_code, 200)
        setup = self.post("two-factor-setup")
        self.assertEqual(setup.status_code, 200)
        secret = setup.json()["secret"]
        self.secrets.update({secret, setup.json()["otpauth_uri"]})
        enabled = self.post("two-factor-enable", {"code": self.code(secret)})
        self.assertEqual(enabled.status_code, 200)
        self.post("logout")
        self.client = APIClient(enforce_csrf_checks=True)
        self.now += timedelta(seconds=30)
        codes = enabled.json()["recovery_codes"]
        self.secrets.update(codes)
        self.secrets.update(code.replace("-", "") for code in codes)
        return secret, codes

    # Setup

    def test_setup_requires_session_and_csrf(self):
        self.token = self.client.get(reverse("login")).json()["csrf_token"]
        self.assertEqual(self.post("two-factor-setup").status_code, 401)
        self.password_login()
        self.assertEqual(self.post("two-factor-setup", token="wrong").status_code, 403)
        self.assertFalse(TOTPDevice.objects.exists())

    def test_setup_returns_secret_uri_and_qr_but_is_off_until_confirmed(self):
        self.password_login()
        body = self.post("two-factor-setup").json()
        self.assertEqual(set(body), {"secret", "otpauth_uri", "qr_code", "csrf_token"})
        self.assertTrue(body["otpauth_uri"].startswith("otpauth://totp/"))
        self.assertIn("issuer=SDU%20Campus%20Assistant", body["otpauth_uri"])
        self.assertTrue(body["qr_code"].startswith("data:image/svg+xml"))
        self.user.refresh_from_db()
        self.assertFalse(self.user.two_factor_enabled)
        state = self.client.get(reverse("security")).json()
        self.assertFalse(state["two_factor_enabled"])

    def test_wrong_code_does_not_enable(self):
        self.password_login()
        secret = self.post("two-factor-setup").json()["secret"]
        wrong = "000000" if self.code(secret) != "000000" else "111111"
        for payload in ({"code": wrong}, {"code": 123456}, {}, {"code": self.code(secret), "x": 1}):
            with self.subTest(payload=payload):
                self.assertEqual(self.post("two-factor-enable", payload).status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.two_factor_enabled)

    def test_enable_returns_ten_single_use_recovery_codes_stored_as_digests(self):
        _, codes = self.enable()
        self.assertEqual(len(set(codes)), 10)
        stored = list(RecoveryCode.objects.filter(user=self.user).values_list("code_hash", flat=True))
        self.assertEqual(len(stored), 10)
        for code in codes:
            self.assertNotIn(code, stored)
            self.assertNotIn(code.replace("-", ""), stored)

    def test_setup_is_refused_while_enabled(self):
        self.enable()
        self.password_login()
        self.verify("000000")
        # Still pending, so the session is anonymous.
        self.assertEqual(self.post("two-factor-setup").status_code, 401)

    # Sign-in

    def test_password_login_without_2fa_is_unchanged(self):
        response = self.password_login()
        self.assertEqual(set(response.json()), {"email", "csrf_token"})

    def test_password_login_with_2fa_holds_session_until_code(self):
        secret, _ = self.enable()
        response = self.password_login()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {
            "two_factor_required", "methods", "email_hint", "email_code_sent", "resend_in", "csrf_token",
        })
        self.assertEqual(response.json()["methods"], ["totp", "recovery"])
        self.assertFalse(response.json()["email_code_sent"])
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(self.client.get(reverse("current-user")).status_code, 401)
        self.assertEqual(self.client.get(reverse("profile")).status_code, 401)

        verified = self.verify(self.code(secret))
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(set(verified.json()), {"email", "csrf_token"})
        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))
        self.assertEqual(self.client.get(reverse("current-user")).status_code, 200)

    def test_verify_without_pending_sign_in_is_refused(self):
        secret, _ = self.enable()
        self.token = self.client.get(reverse("login")).json()["csrf_token"]
        response = self.verify(self.code(secret))
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_pending_sign_in_expires(self):
        secret, _ = self.enable()
        self.password_login()
        session = self.client.session
        session["two_factor_pending"]["expires"] -= 601
        session.save()
        response = self.verify(self.code(secret))
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_code_cannot_be_replayed(self):
        secret, _ = self.enable()
        code = self.code(secret)
        self.password_login()
        self.assertEqual(self.verify(code).status_code, 200)
        other = APIClient(enforce_csrf_checks=True)
        self.password_login(other)
        self.assertEqual(self.verify(code, other).status_code, 400)

    def test_adjacent_step_is_accepted_for_clock_drift(self):
        secret, _ = self.enable()
        self.password_login()
        self.assertEqual(self.verify(self.code(secret, 30)).status_code, 200)

    def test_recovery_code_works_once_in_any_format(self):
        _, codes = self.enable()
        self.password_login()
        response = self.verify(f"  {codes[0].upper().replace('-', ' ')} ")
        self.assertEqual(response.status_code, 200)
        self.post("logout")
        self.client = APIClient(enforce_csrf_checks=True)
        self.password_login()
        self.assertEqual(self.verify(codes[0]).status_code, 400)
        self.assertEqual(self.verify(codes[1]).status_code, 200)
        self.assertEqual(self.client.get(reverse("security")).json()["recovery_codes_remaining"], 8)

    def test_repeated_wrong_codes_lock_the_second_step(self):
        secret, _ = self.enable()
        self.password_login()
        wrong = "000000" if self.code(secret) != "000000" else "111111"
        for _ in range(5):
            self.assertEqual(self.verify(wrong).status_code, 400)
        # Even the right code is refused during the lockout, from any new sign-in.
        self.password_login()
        self.assertEqual(self.verify(self.code(secret)).status_code, 429)
        self.now += timedelta(minutes=6)
        self.assertEqual(self.verify(self.code(secret)).status_code, 200)

    def test_inactive_user_cannot_finish_pending_sign_in(self):
        secret, _ = self.enable()
        self.password_login()
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self.verify(self.code(secret)).status_code, 401)
        self.assertNotIn("_auth_user_id", self.client.session)

    # Disabling

    def test_disable_requires_a_valid_code(self):
        secret, _ = self.enable()
        self.password_login()
        self.token = self.verify(self.code(secret)).json()["csrf_token"]
        self.now += timedelta(seconds=30)
        self.assertEqual(self.post("two-factor-disable", {"method": "totp", "code": "12345"}).status_code, 400)
        self.assertTrue(TOTPDevice.objects.filter(user=self.user).exists())
        response = self.post("two-factor-disable", {"method": "totp", "code": self.code(secret)})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["two_factor_enabled"])
        self.assertFalse(TOTPDevice.objects.filter(user=self.user).exists())
        self.assertFalse(RecoveryCode.objects.filter(user=self.user).exists())
        self.post("logout")
        self.client = APIClient(enforce_csrf_checks=True)
        self.assertEqual(set(self.password_login().json()), {"email", "csrf_token"})

    def test_security_state_reports_only_safe_fields(self):
        self.password_login()
        body = self.client.get(reverse("security")).json()
        self.assertEqual(set(body), {
            "google_available", "google_linked", "has_password", "two_factor_enabled",
            "email_two_factor_enabled", "totp_enabled", "recovery_codes_remaining", "email",
            "email_code_pending", "email_resend_in", "csrf_token",
        })
        self.assertTrue(body["has_password"])

    # Logging

    def test_security_events_are_logged_without_codes_or_secrets(self):
        secret, codes = self.enable()
        self.assertEqual(self.events(), ["setup_started", "code_accepted", "enabled"])
        self.assertIn(f"user={self.user.pk} purpose=enable", self.capture.messages[1])
        wrong = "000000" if self.code(secret) != "000000" else "111111"

        self.password_login()
        self.verify(wrong)
        self.token = self.verify(f" {codes[0]} ").json()["csrf_token"]
        self.assertEqual(self.events()[3:], ["code_invalid", "recovery_code_used"])
        self.assertIn("purpose=sign_in method=totp attempts=1", self.capture.messages[3])
        self.assertIn("remaining=9", self.capture.messages[4])

        self.now += timedelta(seconds=30)
        self.post("two-factor-disable", {"method": "totp", "code": self.code(secret)})
        self.assertEqual(self.events()[5:], ["code_accepted", "disabled"])
        self.assertIn("purpose=disable", self.capture.messages[5])

    def test_lockout_is_logged(self):
        secret, _ = self.enable()
        self.password_login()
        wrong = "000000" if self.code(secret) != "000000" else "111111"
        for _ in range(5):
            self.verify(wrong)
        self.verify(self.code(secret))
        self.assertEqual(self.events()[3:], ["code_invalid"] * 5 + ["locked", "code_refused_locked"])
        self.assertIn("attempts=5", self.capture.messages[7])
