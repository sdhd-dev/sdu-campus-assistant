import logging
import re
import smtplib
from datetime import timedelta
from unittest.mock import patch

import pyotp
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from . import email_codes
from .models import RecoveryCode
from .test_university import Capture

User = get_user_model()
CLIENT_ID = "test-client.apps.googleusercontent.com"


class EmailTwoFactorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "Pine-forest!47-trail"
        cls.user = User.objects.create_user("owner.person@gmail.com", cls.password)

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.now = timezone.now()
        for target in ("accounts.email_codes.timezone.now", "accounts.two_factor.timezone.now"):
            clock = patch(target, side_effect=lambda: self.now)
            clock.start()
            self.addCleanup(clock.stop)
        self.secrets = {self.user.email, self.password, "owner.person"}
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

    def post(self, name, payload=None, client=None):
        return (client or self.client).post(
            reverse(name), payload or {}, format="json", HTTP_X_CSRFTOKEN=self.token,
        )

    def password_login(self):
        self.token = self.client.get(reverse("login")).json()["csrf_token"]
        response = self.post("login", {"email": self.user.email, "password": self.password})
        self.token = response.json().get("csrf_token", self.token)
        return response

    def verify(self, method, code):
        response = self.post("two-factor-verify", {"method": method, "code": code})
        self.token = response.json().get("csrf_token", self.token)
        return response

    def last_code(self):
        return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)

    def wrong(self, code):
        return "000000" if code != "000000" else "111111"

    def sign_out(self):
        self.post("logout")
        self.client = APIClient(enforce_csrf_checks=True)
        self.now += timedelta(seconds=61)

    def enable_email(self, sign_out=True):
        """Signs in, turns email codes on, and returns the recovery codes."""
        self.assertEqual(self.password_login().status_code, 200)
        self.assertEqual(self.post("two-factor-email-code").status_code, 200)
        response = self.post("two-factor-email-enable", {"code": self.last_code()})
        self.assertEqual(response.status_code, 200)
        codes = response.json()["recovery_codes"]
        if codes:
            self.secrets.update(codes)
        if sign_out:
            self.sign_out()
        return codes

    def add_authenticator(self):
        setup = self.post("two-factor-setup").json()
        self.secrets.update({setup["secret"], setup["otpauth_uri"]})
        code = pyotp.TOTP(setup["secret"]).at(self.now)
        self.secrets.add(code)
        response = self.post("two-factor-enable", {"code": code})
        self.assertEqual(response.status_code, 200)
        return setup["secret"], response.json()["recovery_codes"]

    # Turning email codes on

    def test_turning_on_needs_a_code_from_the_account_email_and_gives_recovery_codes(self):
        self.password_login()
        self.assertEqual(self.post("two-factor-email-enable", {"code": "123456"}).status_code, 400)
        sent = self.post("two-factor-email-code")
        self.assertEqual(sent.status_code, 200)
        self.assertTrue(sent.json()["email_code_pending"])
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertIn("security change", mail.outbox[0].subject)
        code = self.last_code()
        self.assertEqual(self.post("two-factor-email-enable", {"code": self.wrong(code)}).status_code, 400)
        response = self.post("two-factor-email-enable", {"code": code})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["email_two_factor_enabled"] and body["two_factor_enabled"])
        self.assertFalse(body["totp_enabled"])
        self.assertEqual(len(set(body["recovery_codes"])), 10)
        self.assertEqual(body["recovery_codes_remaining"], 10)
        stored = set(RecoveryCode.objects.filter(user=self.user).values_list("code_hash", flat=True))
        self.assertFalse(stored & set(body["recovery_codes"]))
        self.assertEqual(self.post("two-factor-email-enable", {"code": code}).status_code, 409)

    def test_requires_session_and_csrf(self):
        self.token = self.client.get(reverse("login")).json()["csrf_token"]
        self.assertEqual(self.post("two-factor-email-code").status_code, 401)
        self.password_login()
        self.token = "wrong"
        self.assertEqual(self.post("two-factor-email-code").status_code, 403)
        self.assertEqual(len(mail.outbox), 0)

    # Signing in

    def test_password_sign_in_sends_a_code_and_needs_it(self):
        self.enable_email()
        response = self.password_login()
        body = response.json()
        self.assertTrue(body["two_factor_required"])
        self.assertEqual(body["methods"], ["email", "recovery"])
        self.assertEqual(body["email_hint"], "o***@gmail.com")
        self.assertTrue(body["email_code_sent"])
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(self.client.get(reverse("profile")).status_code, 401)
        self.assertIn("sign-in code", mail.outbox[-1].subject)
        self.assertEqual(mail.outbox[-1].to, [self.user.email])
        verified = self.verify("email", self.last_code())
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))

    @override_settings(GOOGLE_OAUTH_CLIENT_ID=CLIENT_ID)
    def test_google_sign_in_also_needs_the_email_code(self):
        User.objects.filter(pk=self.user.pk).update(google_subject="google-1")
        self.enable_email()
        start = self.client.get(reverse("google-sign-in")).json()
        self.token = start["csrf_token"]
        claims = {"sub": "google-1", "email": self.user.email, "email_verified": True, "nonce": start["nonce"]}
        with patch("accounts.google.id_token.verify_oauth2_token", return_value=claims):
            response = self.post("google-sign-in", {"credential": "token"})
        self.assertTrue(response.json()["two_factor_required"])
        self.assertNotIn("_auth_user_id", self.client.session)
        self.token = response.json()["csrf_token"]
        self.assertEqual(self.verify("email", self.last_code()).status_code, 200)

    def test_sign_in_code_works_once_and_expires(self):
        self.enable_email()
        self.password_login()
        code = self.last_code()
        self.now += email_codes.CODE_LIFETIME
        self.assertEqual(self.verify("email", code).json()["detail"], "This code has expired. Request a new one.")
        self.now += timedelta(seconds=1)
        self.assertEqual(self.post("two-factor-resend").status_code, 200)
        code = self.last_code()
        self.assertEqual(self.verify("email", code).status_code, 200)
        self.sign_out()
        self.password_login()
        self.assertEqual(self.verify("email", code).status_code, 400)

    def test_five_wrong_codes_burn_it_until_a_new_one_is_sent(self):
        self.enable_email()
        self.password_login()
        code = self.last_code()
        for _ in range(4):
            self.assertEqual(self.verify("email", self.wrong(code)).status_code, 400)
        self.assertEqual(self.verify("email", self.wrong(code)).status_code, 429)
        self.assertEqual(self.verify("email", code).json()["detail"], "Request a new code first.")
        self.now += timedelta(seconds=61)
        self.post("two-factor-resend")
        self.assertEqual(self.verify("email", self.last_code()).status_code, 200)

    def test_resend_is_rate_limited(self):
        self.enable_email()
        self.password_login()
        early = self.post("two-factor-resend")
        self.assertEqual(early.status_code, 429)
        self.assertTrue(0 < early.json()["resend_in"] <= 60)
        self.now += timedelta(seconds=61)
        self.assertEqual(self.post("two-factor-resend").status_code, 200)

    def test_resend_needs_a_pending_sign_in(self):
        self.token = self.client.get(reverse("login")).json()["csrf_token"]
        self.assertEqual(self.post("two-factor-resend").status_code, 401)

    def test_mail_failure_at_sign_in_leaves_the_recovery_code(self):
        codes = self.enable_email()
        with patch("accounts.email_codes._send", side_effect=smtplib.SMTPException("x")):
            body = self.password_login().json()
        self.assertTrue(body["two_factor_required"])
        self.assertFalse(body["email_code_sent"])
        self.assertEqual(self.verify("recovery", codes[0]).status_code, 200)

    def test_unavailable_method_is_refused(self):
        self.enable_email()
        self.password_login()
        self.assertEqual(self.verify("totp", "123456").status_code, 400)
        self.assertEqual(self.post("two-factor-verify", {"code": self.last_code()}).status_code, 400)

    # The authenticator app as an extra method

    def test_authenticator_is_an_extra_method_that_keeps_recovery_codes(self):
        first = self.enable_email(sign_out=False)
        secret, codes = self.add_authenticator()
        self.assertIsNone(codes, "recovery codes come only with the first method")
        self.assertEqual(RecoveryCode.objects.filter(user=self.user).count(), 10)
        self.sign_out()
        body = self.password_login().json()
        self.assertEqual(body["methods"], ["email", "totp", "recovery"])
        self.now += timedelta(seconds=30)
        code = pyotp.TOTP(secret).at(self.now)
        self.secrets.add(code)
        self.assertEqual(self.verify("totp", code).status_code, 200)
        self.assertTrue(first)

    def test_authenticator_first_then_email_keeps_the_first_codes(self):
        self.password_login()
        _, codes = self.add_authenticator()
        self.assertEqual(len(codes), 10)
        self.secrets.update(codes)
        self.now += timedelta(seconds=30)
        self.post("two-factor-email-code")
        response = self.post("two-factor-email-enable", {"code": self.last_code()})
        self.assertIsNone(response.json()["recovery_codes"])

    # Turning off

    def test_turning_off_with_an_email_code_ends_two_step_verification(self):
        self.enable_email(sign_out=False)
        self.now += timedelta(seconds=61)
        self.post("two-factor-email-code")
        code = self.last_code()
        self.assertEqual(self.post("two-factor-email-disable", {"method": "email", "code": "12"}).status_code, 400)
        response = self.post("two-factor-email-disable", {"method": "email", "code": code})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["two_factor_enabled"])
        self.assertFalse(RecoveryCode.objects.filter(user=self.user).exists())
        self.sign_out()
        self.assertEqual(set(self.password_login().json()), {"email", "csrf_token"})

    def test_turning_off_with_a_recovery_code(self):
        codes = self.enable_email(sign_out=False)
        response = self.post("two-factor-email-disable", {"method": "recovery", "code": codes[3]})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["email_two_factor_enabled"])

    def test_a_sign_in_code_cannot_authorise_turning_off(self):
        self.enable_email(sign_out=False)
        # A valid sign-in code exists, but changes need a code sent for that purpose.
        self.now += timedelta(seconds=61)
        email_codes.issue(self.user, email_codes.SIGN_IN, self.user.email)
        response = self.post("two-factor-email-disable", {"method": "email", "code": self.last_code()})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Request a new code first.")
        self.assertTrue(User.objects.get(pk=self.user.pk).email_two_factor)

    def test_removing_the_authenticator_keeps_email_codes_and_recovery_codes(self):
        self.enable_email(sign_out=False)
        secret, _ = self.add_authenticator()
        self.now += timedelta(seconds=30)
        code = pyotp.TOTP(secret).at(self.now)
        self.secrets.add(code)
        response = self.post("two-factor-disable", {"method": "totp", "code": code})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["totp_enabled"])
        self.assertTrue(body["two_factor_enabled"])
        self.assertEqual(body["recovery_codes_remaining"], 10)

    # Logging

    def test_events_are_logged_without_codes_or_addresses(self):
        self.enable_email()
        self.password_login()
        self.verify("email", self.wrong(self.last_code()))
        self.verify("email", self.last_code())
        self.assertEqual(self.events(), [
            "code_sent", "enabled", "code_sent", "code_invalid", "code_accepted",
        ])
        self.assertIn("purpose=security", self.capture.messages[0])
        self.assertIn("method=email recovery_codes=10", self.capture.messages[1])
        self.assertIn("purpose=sign_in", self.capture.messages[2])
        self.assertIn("o***@gmail.com", self.capture.messages[2])
        self.assertIn("purpose=sign_in method=email", self.capture.messages[4])
