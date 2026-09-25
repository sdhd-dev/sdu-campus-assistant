import json
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.sessions.models import Session
from django.db import OperationalError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

User = get_user_model()
PRIVILEGE_FIELDS = {
    "is_staff": True,
    "is_superuser": True,
    "is_active": False,
    "groups": [],
    "user_permissions": [],
    "email": "attacker@example.com",
    "password": "Pine-forest!47-trail",
    "id": 1,
    "pk": 1,
    "last_login": None,
    "unexpected": "value",
}


class ProfileTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "Pine-forest!47-trail"
        cls.user = User.objects.create_user("student@sdu.edu.kz", cls.password)
        cls.other = User.objects.create_user("other@sdu.edu.kz", cls.password)

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.url = reverse("profile")
        self.token = self.sign_in()

    def sign_in(self, client=None):
        client = client or self.client
        login_url = reverse("login")
        token = client.get(login_url).json()["csrf_token"]
        response = client.post(
            login_url, {"email": self.user.email, "password": self.password},
            format="json", HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["csrf_token"]

    def patch(self, payload, token=None, **headers):
        return self.client.patch(
            self.url, payload, format="json",
            HTTP_X_CSRFTOKEN=self.token if token is None else token, **headers,
        )

    def assertAdministrativeFlagsUnchanged(self, user=None):
        user = user or self.user
        user.refresh_from_db()
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.is_active)
        self.assertFalse(user.groups.exists())
        self.assertFalse(user.user_permissions.exists())
        self.assertEqual(user.email, "student@sdu.edu.kz")
        self.assertTrue(user.check_password(self.password))

    # Unauthenticated access

    def test_anonymous_invalid_and_expired_sessions_cannot_read_or_write(self):
        anonymous = APIClient(enforce_csrf_checks=True)
        token = anonymous.get(reverse("login")).json()["csrf_token"]
        for method in ("get", "patch"):
            response = getattr(anonymous, method)(
                self.url, {"profile_type": "STUDENT"}, format="json", HTTP_X_CSRFTOKEN=token,
            )
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json(), {"detail": "Authentication required."})
            self.assertIn("no-store", response.headers["Cache-Control"])

        anonymous.cookies[settings.SESSION_COOKIE_NAME] = "invalid-session"
        self.assertEqual(anonymous.get(self.url).status_code, 401)

        Session.objects.filter(session_key=self.client.session.session_key).update(
            expire_date=timezone.now() - timedelta(seconds=1)
        )
        expired = self.patch({"profile_type": "STUDENT"})
        self.assertEqual(expired.status_code, 401)
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile_type, User.ProfileType.VISITOR)

    def test_deactivated_account_loses_profile_access(self):
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(self.patch({"profile_type": "STAFF"}).status_code, 401)
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile_type, User.ProfileType.VISITOR)

    # Reading

    def test_get_returns_session_account_with_only_safe_fields(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body), {"email", "profile_type", "profile_types", "csrf_token"})
        self.assertEqual(body["email"], self.user.email)
        self.assertEqual(body["profile_type"], User.ProfileType.VISITOR)
        self.assertEqual(body["profile_types"], [
            {"value": "STUDENT", "label": "Student"},
            {"value": "STAFF", "label": "Staff"},
            {"value": "VISITOR", "label": "Visitor"},
        ])
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertNotContains(response, self.user.password)
        self.assertNotContains(response, self.other.email)

    # Valid updates

    def test_every_supported_value_is_saved_and_returned(self):
        for value in User.ProfileType.values:
            with self.subTest(profile_type=value):
                response = self.patch({"profile_type": value})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["profile_type"], value)
                self.assertEqual(response.json()["email"], self.user.email)
                self.user.refresh_from_db()
                self.assertEqual(self.user.profile_type, value)
        self.assertAdministrativeFlagsUnchanged()

    def test_saved_selection_survives_logout_and_a_later_login(self):
        self.assertEqual(self.patch({"profile_type": "STUDENT"}).status_code, 200)
        self.assertEqual(
            self.client.post(reverse("logout"), HTTP_X_CSRFTOKEN=self.token).status_code, 204
        )
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.token = self.sign_in()
        self.assertEqual(self.client.get(self.url).json()["profile_type"], "STUDENT")

    def test_update_touches_only_the_profile_column_of_the_session_user(self):
        group = Group.objects.create(name="campus-admins")
        group.permissions.add(Permission.objects.first())
        self.other.profile_type = User.ProfileType.STUDENT
        self.other.is_staff = True
        self.other.save()

        self.assertEqual(self.patch({"profile_type": "STAFF"}).status_code, 200)

        self.assertAdministrativeFlagsUnchanged()
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile_type, "STAFF")
        self.other.refresh_from_db()
        self.assertEqual(self.other.profile_type, User.ProfileType.STUDENT)
        self.assertTrue(self.other.is_staff)

    def test_staff_affiliation_grants_no_administrative_access(self):
        self.assertEqual(self.patch({"profile_type": "STAFF"}).status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)
        self.assertFalse(self.user.has_perm("accounts.change_user"))
        self.assertEqual(self.user.get_all_permissions(), set())

    # Invalid updates

    def test_unsupported_values_are_rejected_without_echoing_input(self):
        for value in ("ADMIN", "student", "", " STUDENT ", "STUDENT,STAFF", "x" * 200):
            with self.subTest(profile_type=value):
                response = self.patch({"profile_type": value})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.json(), {"profile_type": ["Choose Student, Staff, or Visitor."]}
                )
        for value in (None, 1, True, ["STUDENT"], {"value": "STUDENT"}):
            with self.subTest(profile_type=value):
                response = self.patch({"profile_type": value})
                self.assertEqual(response.status_code, 400)
                self.assertIn("profile_type", response.json())
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile_type, User.ProfileType.VISITOR)

    def test_privilege_and_unknown_fields_are_rejected_even_alongside_a_valid_value(self):
        for name, value in PRIVILEGE_FIELDS.items():
            with self.subTest(field=name):
                response = self.patch({"profile_type": "STUDENT", name: value})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.json(), {"non_field_errors": ["Only profile_type is accepted."]}
                )
                response = self.patch({name: value})
                self.assertEqual(response.status_code, 400)
                self.assertIn("non_field_errors", response.json())
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile_type, User.ProfileType.VISITOR)
        self.assertAdministrativeFlagsUnchanged()
        self.other.refresh_from_db()
        self.assertEqual(self.other.email, "other@sdu.edu.kz")

    def test_missing_field_and_malformed_bodies_are_rejected(self):
        for payload in ({}, [], "text", None, [{"profile_type": "STUDENT"}]):
            with self.subTest(payload=payload):
                response = self.client.patch(
                    self.url, json.dumps(payload), content_type="application/json",
                    HTTP_X_CSRFTOKEN=self.token,
                )
                self.assertEqual(response.status_code, 400)
        response = self.client.patch(
            self.url, '{"profile_type":', content_type="application/json",
            HTTP_X_CSRFTOKEN=self.token,
        )
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile_type, User.ProfileType.VISITOR)

    # CSRF and method restrictions

    def test_update_requires_csrf_token_cookie_and_trusted_origin(self):
        cases = [
            ("no token", {}),
            ("wrong token", {"HTTP_X_CSRFTOKEN": "invalid"}),
            ("stale token", {"HTTP_X_CSRFTOKEN": "a" * 64}),
            ("untrusted origin", {
                "HTTP_X_CSRFTOKEN": self.token, "HTTP_ORIGIN": "https://untrusted.example",
            }),
        ]
        for label, headers in cases:
            with self.subTest(case=label):
                response = self.client.patch(
                    self.url, {"profile_type": "STAFF"}, format="json", **headers
                )
                self.assertEqual(response.status_code, 403)
                self.user.refresh_from_db()
                self.assertEqual(self.user.profile_type, User.ProfileType.VISITOR)

        without_cookie = APIClient(enforce_csrf_checks=True)
        without_cookie.cookies[settings.SESSION_COOKIE_NAME] = \
            self.client.cookies[settings.SESSION_COOKIE_NAME].value
        self.assertEqual(without_cookie.patch(
            self.url, {"profile_type": "STAFF"}, format="json", HTTP_X_CSRFTOKEN=self.token,
        ).status_code, 403)

        # The session still works, and a correctly signed request succeeds.
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.patch(
            {"profile_type": "STAFF"}, HTTP_ORIGIN="http://127.0.0.1:5173"
        ).status_code, 200)

    def test_unsafe_methods_other_than_patch_are_not_allowed(self):
        for method in ("post", "put", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    self.url, {"profile_type": "STAFF"}, format="json",
                    HTTP_X_CSRFTOKEN=self.token,
                )
                self.assertEqual(response.status_code, 405)
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile_type, User.ProfileType.VISITOR)

    def test_database_error_while_saving_has_a_generic_response(self):
        with patch("accounts.serializers.ProfileSerializer.update",
                   side_effect=OperationalError("private database details")):
            response = self.patch({"profile_type": "STUDENT"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {
            "detail": "Saving your profile is temporarily unavailable. Please try again."
        })
        self.assertNotContains(response, "private", status_code=503)
