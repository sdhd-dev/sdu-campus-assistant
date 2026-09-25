import logging
import re
import smtplib
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from . import email_codes, google, university
from .models import EmailCode, EmailCodeSend

User = get_user_model()
STUDENT_EMAIL = "a.student@stu.sdu.edu.kz"
STAFF_EMAIL = "b.teacher@sdu.edu.kz"


class Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


@override_settings(
    UNIVERSITY_STUDENT_DOMAINS=frozenset({"stu.sdu.edu.kz"}),
    UNIVERSITY_STAFF_DOMAINS=frozenset({"sdu.edu.kz"}),
)
class UniversityEmailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "Pine-forest!47-trail"
        cls.user = User.objects.create_user("person@gmail.com", cls.password)
        cls.other = User.objects.create_user("someone@gmail.com", cls.password)

    def setUp(self):
        self.now = timezone.now()
        clock = patch("accounts.email_codes.timezone.now", side_effect=lambda: self.now)
        clock.start()
        self.addCleanup(clock.stop)
        self.capture = Capture()
        logs = patch.object(logging.getLogger("accounts"), "handlers", [self.capture])
        logs.start()
        self.addCleanup(logs.stop)
        self.addCleanup(self.assertLogsHideSecrets)
        self.client, self.token = self.sign_in(self.user)

    def sign_in(self, user):
        client = APIClient(enforce_csrf_checks=True)
        token = client.get(reverse("login")).json()["csrf_token"]
        response = client.post(reverse("login"), {"email": user.email, "password": self.password},
                               format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        return client, response.json()["csrf_token"]

    def post(self, name, payload=None, client=None, token=None):
        return (client or self.client).post(
            reverse(name), payload or {}, format="json", HTTP_X_CSRFTOKEN=token or self.token,
        )

    def start(self, email=STUDENT_EMAIL, role=None, **kwargs):
        role = role or ("STAFF" if email.strip().lower().endswith("@sdu.edu.kz") else "STUDENT")
        return self.post("verification-start", {"email": email, "role": role}, **kwargs)

    def confirm(self, code, **kwargs):
        return self.post("verification-confirm", {"code": code}, **kwargs)

    def last_code(self):
        return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)

    def wrong(self, code):
        return "000000" if code != "000000" else "111111"

    def assertLogsHideSecrets(self):
        codes = {m for message in mail.outbox for m in re.findall(r"\b\d{6}\b", message.body)}
        for message in self.capture.messages:
            for secret in (STUDENT_EMAIL, STAFF_EMAIL, *codes):
                self.assertNotIn(secret, message)

    def logged(self, event):
        return [message for message in self.capture.messages if message.startswith(event)]

    # Availability and access

    @override_settings(UNIVERSITY_STUDENT_DOMAINS=frozenset(), UNIVERSITY_STAFF_DOMAINS=frozenset())
    def test_disabled_without_domains(self):
        self.assertEqual(self.client.get(reverse("verification")).status_code, 404)
        self.assertEqual(self.start().status_code, 404)
        self.assertEqual(len(mail.outbox), 0)

    def test_requires_session_and_csrf(self):
        anonymous = APIClient(enforce_csrf_checks=True)
        self.assertEqual(anonymous.get(reverse("verification")).status_code, 401)
        self.assertEqual(self.start(token="wrong").status_code, 403)
        self.assertEqual(len(mail.outbox), 0)

    def test_state_shape(self):
        body = self.client.get(reverse("verification")).json()
        self.assertEqual(set(body), {
            "profile_type", "verified_affiliation", "university_email", "verified_at", "pending_email",
            "resend_in", "student_domains", "staff_domains", "csrf_token",
        })
        self.assertIsNone(body["verified_affiliation"])
        self.assertEqual(body["student_domains"], ["stu.sdu.edu.kz"])
        self.assertEqual(body["staff_domains"], ["sdu.edu.kz"])

    # Requesting a code

    def test_only_exact_university_domains_are_accepted(self):
        for email in ("person@gmail.com", "x@evil.sdu.edu.kz", "x@sdu.edu.kz.evil.com", "not-an-email", 42):
            with self.subTest(email=email):
                response = self.post("verification-start", {"email": email, "role": "STUDENT"})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["detail"], "Enter your SDU student or staff email address.")
        for payload in (
            {"email": STUDENT_EMAIL}, {}, {"email": STUDENT_EMAIL, "role": "VISITOR"},
            {"email": STUDENT_EMAIL, "role": "student"}, {"email": STUDENT_EMAIL, "role": "STUDENT", "x": 1},
        ):
            with self.subTest(payload=payload):
                self.assertEqual(self.post("verification-start", payload).status_code, 400)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(EmailCode.objects.exists())

    def test_code_is_sent_and_only_a_digest_is_stored(self):
        response = self.start("  A.Student@STU.sdu.edu.kz ")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pending_email"], STUDENT_EMAIL)
        self.assertEqual(mail.outbox[0].to, [STUDENT_EMAIL])
        code = self.last_code()
        challenge = EmailCode.objects.get(user=self.user)
        self.assertEqual(len(challenge.code_hash), 64)
        self.assertNotIn(code, challenge.code_hash)
        self.assertEqual(len(self.logged("code_sent")), 1)

    def test_address_verified_elsewhere_gets_no_email_but_the_same_answer(self):
        normal = self.start().json()
        User.objects.filter(pk=self.other.pk).update(
            university_email=STAFF_EMAIL, verified_affiliation="STAFF",
            affiliation_verified_at=self.now, affiliation_source="EMAIL",
        )
        self.now += timedelta(minutes=2)
        taken = self.start(STAFF_EMAIL)
        self.assertEqual(taken.status_code, 200)
        self.assertEqual(taken.json()["detail"], normal["detail"])
        self.assertEqual(set(taken.json()), set(normal))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(len(self.logged("code_withheld")), 1)
        # Guessing cannot help: no one knows the code, and attempts are limited.
        self.assertEqual(self.confirm("123456").status_code, 400)

    def test_resend_cooldown_and_hourly_limit_per_account(self):
        self.assertEqual(self.start().status_code, 200)
        early = self.start()
        self.assertEqual(early.status_code, 429)
        self.assertTrue(0 < early.json()["retry_after"] <= 60)
        for _ in range(4):
            self.now += timedelta(seconds=61)
            self.assertEqual(self.start().status_code, 200)
        self.now += timedelta(seconds=61)
        limited = self.start()
        self.assertEqual(limited.status_code, 429)
        self.assertGreater(limited.json()["retry_after"], 60)
        self.assertEqual(len(mail.outbox), 5)
        self.assertTrue(self.logged("code_rate_limited"))
        self.now += timedelta(hours=1)
        self.assertEqual(self.start().status_code, 200)

    def test_hourly_limit_per_address_across_accounts(self):
        for index in range(5):
            user = User.objects.create_user(f"user{index}@gmail.com", self.password)
            client, token = self.sign_in(user)
            self.assertEqual(self.start(client=client, token=token).status_code, 200)
        self.assertEqual(self.start().status_code, 429)
        self.assertEqual(len(mail.outbox), 5)

    def test_mail_failure_is_503_and_records_nothing(self):
        with patch("accounts.email_codes._send", side_effect=smtplib.SMTPException("x@stu.sdu.edu.kz")):
            self.assertEqual(self.start().status_code, 503)
        self.assertFalse(EmailCode.objects.exists())
        self.assertFalse(EmailCodeSend.objects.exists())
        self.assertEqual(self.logged("code_send_failed")[0].split()[-1], "error=SMTPException")
        self.assertEqual(self.start().status_code, 200)

    # Confirming

    def test_domain_must_match_the_chosen_role(self):
        student = self.start(STUDENT_EMAIL, role="STAFF")
        self.assertEqual(student.status_code, 400)
        self.assertEqual(student.json()["detail"], "This is a student address. Choose Student to verify it.")
        staff = self.start(STAFF_EMAIL, role="STUDENT")
        self.assertEqual(staff.json()["detail"], "This is a staff address. Choose Staff to verify it.")
        self.assertEqual(len(mail.outbox), 0)

    def test_student_code_verifies_and_sets_the_role_without_permissions(self):
        self.start()
        response = self.confirm(self.last_code())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["verified_affiliation"], "STUDENT")
        self.assertEqual(response.json()["profile_type"], "STUDENT")
        self.assertEqual(response.json()["university_email"], STUDENT_EMAIL)
        self.assertIsNone(response.json()["pending_email"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.verified_affiliation, "STUDENT")
        self.assertEqual(self.user.affiliation_source, "EMAIL")
        self.assertEqual(self.user.profile_type, "STUDENT")
        self.assertFalse(self.user.is_staff or self.user.is_superuser)
        self.assertEqual(len(self.logged("verified")), 1)

    def test_staff_domain_gives_staff(self):
        self.start(STAFF_EMAIL)
        body = self.confirm(self.last_code()).json()
        self.assertEqual((body["verified_affiliation"], body["profile_type"]), ("STAFF", "STAFF"))

    def test_verifying_the_other_role_replaces_the_first(self):
        self.start()
        self.confirm(self.last_code())
        self.now += timedelta(seconds=61)
        self.start(STAFF_EMAIL)
        body = self.confirm(self.last_code()).json()
        self.assertEqual((body["verified_affiliation"], body["profile_type"]), ("STAFF", "STAFF"))
        self.assertEqual(body["university_email"], STAFF_EMAIL)

    def test_failed_verification_keeps_the_previous_role(self):
        self.start()
        self.confirm(self.wrong(self.last_code()))
        self.post("verification-cancel")
        self.assertEqual(User.objects.get(pk=self.user.pk).profile_type, "VISITOR")

    def test_code_works_once(self):
        self.start()
        code = self.last_code()
        self.assertEqual(self.confirm(code).status_code, 200)
        self.assertEqual(self.confirm(code).status_code, 400)

    def test_code_expires(self):
        self.start()
        self.now += email_codes.CODE_LIFETIME
        response = self.confirm(self.last_code())
        self.assertEqual(response.status_code, 400)
        self.assertIn("expired", response.json()["detail"])
        self.assertIsNone(User.objects.get(pk=self.user.pk).verified_affiliation)

    def test_resend_replaces_the_previous_code(self):
        self.start()
        first = self.last_code()
        self.now += timedelta(seconds=61)
        self.start()
        second = self.last_code()
        if first != second:
            self.assertEqual(self.confirm(first).status_code, 400)
        self.assertEqual(self.confirm(second).status_code, 200)

    def test_five_wrong_codes_burn_the_code(self):
        self.start()
        code = self.last_code()
        for attempt in range(1, 5):
            self.assertEqual(self.confirm(self.wrong(code)).status_code, 400)
        self.assertEqual(self.confirm(self.wrong(code)).status_code, 429)
        self.assertEqual(self.confirm(code).status_code, 400)
        self.assertEqual(len(self.logged("code_invalid")), 4)
        self.assertEqual(len(self.logged("code_locked")), 1)

    def test_malformed_codes_count_as_wrong(self):
        self.start()
        for payload in ({"code": "12345"}, {"code": 123456}, {}, {"code": "123456", "x": 1}):
            with self.subTest(payload=payload):
                self.assertEqual(self.post("verification-confirm", payload).status_code, 400)

    def test_second_account_confirming_the_same_address_gets_409(self):
        other, other_token = self.sign_in(self.other)
        self.start()
        mine = self.last_code()
        self.start(client=other, token=other_token)
        theirs = self.last_code()
        self.assertEqual(self.confirm(mine).status_code, 200)
        conflict = self.confirm(theirs, client=other, token=other_token)
        self.assertEqual(conflict.status_code, 409)
        self.assertIsNone(User.objects.get(pk=self.other.pk).university_email)
        self.assertEqual(len(self.logged("verification_conflict")), 1)

    def test_domain_removed_from_settings_before_confirm(self):
        self.start()
        with self.settings(UNIVERSITY_STUDENT_DOMAINS=frozenset({"new.sdu.edu.kz"})):
            self.assertEqual(self.confirm(self.last_code()).status_code, 400)
        self.assertIsNone(User.objects.get(pk=self.user.pk).verified_affiliation)

    # Cancelling and removing

    def test_cancel_clears_the_pending_code(self):
        self.start()
        response = self.post("verification-cancel")
        self.assertIsNone(response.json()["pending_email"])
        self.assertEqual(self.confirm(self.last_code()).status_code, 400)

    def test_remove_clears_status_and_frees_the_address(self):
        self.start()
        self.confirm(self.last_code())
        removed = self.client.delete(reverse("verification"), HTTP_X_CSRFTOKEN=self.token)
        self.assertEqual(removed.status_code, 200)
        self.assertIsNone(removed.json()["verified_affiliation"])
        self.assertEqual(removed.json()["profile_type"], "VISITOR")
        self.assertEqual(len(self.logged("verification_removed")), 1)
        other, other_token = self.sign_in(self.other)
        self.start(client=other, token=other_token)
        self.assertEqual(self.confirm(self.last_code(), client=other, token=other_token).status_code, 200)

    # Groundwork for Google Workspace

    def test_domain_mapping_is_exact_and_case_insensitive(self):
        self.assertEqual(university.affiliation_for_domain("STU.SDU.EDU.KZ"), "STUDENT")
        self.assertEqual(university.affiliation_for_domain("sdu.edu.kz"), "STAFF")
        for domain in ("x.sdu.edu.kz", "gmail.com", "", None):
            self.assertIsNone(university.affiliation_for_domain(domain))

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="client")
    def test_google_identity_carries_the_hosted_domain(self):
        claims = {"sub": "1", "email": "a@stu.sdu.edu.kz", "email_verified": True,
                  "nonce": "n", "hd": "stu.sdu.edu.kz"}
        with patch("accounts.google.id_token.verify_oauth2_token", return_value=claims):
            self.assertEqual(google.verify_credential("token", "n")["hosted_domain"], "stu.sdu.edu.kz")
