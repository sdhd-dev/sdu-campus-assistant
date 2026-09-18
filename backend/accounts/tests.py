import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import password_validators_help_texts
from django.db import IntegrityError, OperationalError, connections, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .serializers import RegistrationSerializer

User = get_user_model()


class UserTests(TestCase):
    def test_email_authentication_and_password_hashing(self):
        user = User.objects.create_user(" Student@SDU.edu.kz ", "test-only-password")
        self.assertEqual(user.email, "student@sdu.edu.kz")
        self.assertNotEqual(user.password, "test-only-password")
        self.assertTrue(user.check_password("test-only-password"))
        self.assertEqual(authenticate(email="STUDENT@sdu.edu.kz", password="test-only-password"), user)
        self.assertIsNone(authenticate(email=user.email, password="wrong-password"))

    def test_profile_types_do_not_grant_privileges(self):
        for profile_type in User.ProfileType.values:
            with self.subTest(profile_type=profile_type):
                user = User.objects.create_user(f"{profile_type}@example.com", profile_type=profile_type)
                user.refresh_from_db()
                self.assertFalse(user.is_staff)
                self.assertFalse(user.is_superuser)
                self.assertFalse(user.has_usable_password())

    def test_database_rejects_case_insensitive_duplicate_email(self):
        User.objects.create_user("student@example.com")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create(email="STUDENT@example.com")

    def test_database_rejects_invalid_profile_type(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("student@example.com", profile_type="ADMIN")

    def test_superuser_flags_are_explicit_and_independent(self):
        user = User.objects.create_superuser("admin@example.com", "test-only-password")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.profile_type, User.ProfileType.VISITOR)
        for flags in ({"is_staff": False}, {"is_superuser": False}):
            with self.assertRaises(ValueError):
                User.objects.create_superuser("invalid@example.com", **flags)

    def test_email_is_required(self):
        for email in (None, "", "   "):
            with self.assertRaises(ValueError):
                User.objects.create_user(email)


class RegistrationTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.url = reverse("register")
        self.csrf_token = self.client.get(self.url).json()["csrf_token"]
        self.payload = {
            "email": "New.Student@SDU.edu.kz",
            "password": "Pine-forest!47-trail",
            "password_confirmation": "Pine-forest!47-trail",
        }

    def post(self, payload=None, **headers):
        return self.client.post(
            self.url, self.payload if payload is None else payload,
            format="json", HTTP_X_CSRFTOKEN=self.csrf_token, **headers,
        )

    def test_success_persists_hashed_password_and_only_returns_email_without_login(self):
        response = self.post(HTTP_ORIGIN="http://127.0.0.1:5173")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"email": "new.student@sdu.edu.kz"})
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        user = User.objects.get(email=response.json()["email"])
        self.assertTrue(user.check_password(self.payload["password"]))
        self.assertNotEqual(user.password, self.payload["password"])
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.profile_type, User.ProfileType.VISITOR)
        self.assertFalse(user.groups.exists())
        self.assertFalse(user.user_permissions.exists())
        self.assertIsNone(user.last_login)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertNotIn("sessionid", response.cookies)
        self.assertNotContains(response, self.payload["password"], status_code=201)
        self.assertNotContains(response, user.password, status_code=201)

    def test_configuration_matches_configured_password_validators(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {"csrf_token", "password_requirements"})
        self.assertEqual(response.json()["password_requirements"], password_validators_help_texts())
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertIn("csrftoken", response.cookies)
        self.assertEqual(User.objects.count(), 0)

    def test_each_password_validator_is_enforced(self):
        for password, code in (
            ("xQ!7", "at least 8 characters"),
            ("password", "too common"),
            ("947582619305", "entirely numeric"),
            ("new.student@sdu.edu.kz", "too similar"),
        ):
            with self.subTest(code=code):
                response = self.post({**self.payload, "password": password, "password_confirmation": password})
                self.assertEqual(response.status_code, 400)
                self.assertIn(code, " ".join(response.json()["password"]))
        self.assertEqual(User.objects.count(), 0)

    def test_missing_invalid_and_mismatched_input(self):
        cases = [({}, "email"), ({**self.payload, "email": "invalid"}, "email"),
                 ({**self.payload, "password_confirmation": "different"}, "password_confirmation"),
                 ({**self.payload, "email": "a" * 255 + "@example.com"}, "email")]
        for field in self.payload:
            cases.append(({key: value for key, value in self.payload.items() if key != field}, field))
            for value in ("", None, 123456789, True, [], {}):
                cases.append(({**self.payload, field: value}, field))
        for field in ("password", "password_confirmation"):
            cases.append(({**self.payload, field: "x" * 129}, field))
        for payload, field in cases:
            with self.subTest(field=field):
                response = self.post(payload)
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())
        for payload in ([], "not an object", None):
            response = self.client.post(self.url, data=json.dumps(payload),
                                        content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf_token)
            self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.count(), 0)

    def test_password_whitespace_is_preserved(self):
        password = "  Pine-forest!47-trail  "
        response = self.post({**self.payload, "password": password, "password_confirmation": password})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.get().check_password(password))
        self.assertFalse(User.objects.get().check_password(password.strip()))

    def test_duplicate_email_policy_includes_case_and_surrounding_whitespace(self):
        User.objects.create_user("new.student@sdu.edu.kz")
        for email in ("new.student@sdu.edu.kz", "NEW.STUDENT@SDU.EDU.KZ", "  New.Student@SDU.edu.kz  "):
            response = self.post({**self.payload, "email": email})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json(), {"email": ["An account with this email already exists."]})
        self.assertEqual(User.objects.count(), 1)

    def test_normalizes_surrounding_whitespace_on_creation(self):
        response = self.post({**self.payload, "email": "  New.Student@SDU.edu.kz  "})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(User.objects.get().email, "new.student@sdu.edu.kz")

    def test_rejects_privilege_profile_and_all_other_unintended_fields(self):
        for name, value in {
            "is_staff": True, "is_superuser": True, "groups": [],
            "user_permissions": [], "profile_type": "STAFF", "is_active": False,
            "id": 1, "first_name": "Name", "unexpected": "value",
        }.items():
            with self.subTest(field=name):
                response = self.post({**self.payload, name: value})
                self.assertEqual(response.status_code, 400)
                self.assertIn("non_field_errors", response.json())
        self.assertEqual(User.objects.count(), 0)

    def test_database_duplicate_after_validation_returns_field_error(self):
        original_create = RegistrationSerializer.create

        def competing_registration(serializer, validated_data):
            User.objects.create_user(validated_data["email"])
            return original_create(serializer, validated_data)

        with patch.object(RegistrationSerializer, "create", competing_registration):
            response = self.post()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"email": ["An account with this email already exists."]})
        self.assertEqual(User.objects.count(), 1)

    def test_database_outage_does_not_expose_details(self):
        for target in ("accounts.serializers.RegistrationSerializer.validate_email",
                       "accounts.serializers.RegistrationSerializer.create"):
            with patch(target, side_effect=OperationalError("private database details")):
                response = self.post()
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json(), {"detail": "Registration is temporarily unavailable. Please try again."})
            self.assertNotContains(response, "private", status_code=503)
            self.assertNotContains(response, self.payload["password"], status_code=503)

    def test_anonymous_registration_requires_csrf_and_trusted_origin(self):
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, 403)
        response = self.post(HTTP_ORIGIN="https://untrusted.example")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(User.objects.count(), 0)

    def test_other_methods_and_malformed_json_are_rejected(self):
        for method in ("put", "patch", "delete"):
            response = getattr(self.client, method)(self.url, {}, format="json", HTTP_X_CSRFTOKEN=self.csrf_token)
            self.assertEqual(response.status_code, 405)
        response = self.client.post(self.url, '{"email":', content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf_token)
        self.assertEqual(response.status_code, 400)


class ConcurrentRegistrationTests(TransactionTestCase):
    def test_competing_requests_create_exactly_one_account(self):
        barrier = Barrier(2, timeout=10)
        original_validate = RegistrationSerializer.validate_email

        def validate_then_wait(serializer, value):
            value = original_validate(serializer, value)
            barrier.wait()
            return value

        def register(email):
            try:
                client = APIClient(enforce_csrf_checks=True)
                url = reverse("register")
                token = client.get(url).json()["csrf_token"]
                response = client.post(url, {
                    "email": email,
                    "password": "Pine-forest!47-trail",
                    "password_confirmation": "Pine-forest!47-trail",
                }, format="json", HTTP_X_CSRFTOKEN=token)
                return response.status_code, response.json()
            finally:
                connections.close_all()

        with patch.object(RegistrationSerializer, "validate_email", validate_then_wait):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(register, ["race@example.com", "RACE@EXAMPLE.COM"]))
        self.assertEqual(sorted(status for status, _ in results), [201, 400])
        self.assertEqual(User.objects.filter(email__iexact="race@example.com").count(), 1)
        self.assertIn((400, {"email": ["An account with this email already exists."]}), results)
