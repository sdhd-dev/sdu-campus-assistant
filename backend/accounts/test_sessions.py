import json
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db import OperationalError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

User = get_user_model()


class SessionAuthenticationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "  Pine-forest!47-trail  "
        cls.user = User.objects.create_user("student@sdu.edu.kz", cls.password)
        cls.inactive = User.objects.create_user("inactive@sdu.edu.kz", cls.password, is_active=False)

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.login_url = reverse("login")
        self.logout_url = reverse("logout")
        self.me_url = reverse("current-user")
        self.token = self.client.get(self.login_url).json()["csrf_token"]

    def login(self, **overrides):
        return self.client.post(self.login_url, {
            "email": self.user.email, "password": self.password, **overrides,
        }, format="json", HTTP_X_CSRFTOKEN=self.token)

    def test_login_restores_authenticated_access_with_only_safe_fields(self):
        response = self.login(email="  STUDENT@SDU.EDU.KZ  ")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {"email", "csrf_token"})
        self.assertEqual(response.json()["email"], self.user.email)
        self.assertIn("no-store", response.headers["Cache-Control"])
        cookie = response.cookies[settings.SESSION_COOKIE_NAME]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.last_login)
        # A new client with only the cookie proves restoration is server-side.
        refreshed = APIClient(enforce_csrf_checks=True)
        refreshed.cookies[settings.SESSION_COOKIE_NAME] = cookie.value
        current = refreshed.get(self.me_url)
        self.assertEqual(current.status_code, 200)
        self.assertEqual(set(current.json()), {"email", "csrf_token"})
        self.assertEqual(current.json()["email"], self.user.email)
        self.assertIn("no-store", current.headers["Cache-Control"])
        for result in (response, current):
            self.assertNotContains(result, self.password)
            self.assertNotContains(result, self.user.password)

    def test_wrong_password_unknown_email_and_inactive_account_share_generic_error(self):
        for overrides in ({"password": "wrong"}, {"email": "unknown@sdu.edu.kz"},
                          {"email": self.inactive.email}, {"password": self.password.strip()}):
            with self.subTest(overrides=list(overrides)):
                response = self.login(**overrides)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json(), {"detail": "Invalid email or password."})
                self.assertNotIn("_auth_user_id", self.client.session)
        self.inactive.refresh_from_db()
        self.assertIsNone(self.inactive.last_login)

    def test_current_user_rejects_anonymous_invalid_and_expired_sessions(self):
        self.assertEqual(self.client.get(self.me_url).status_code, 401)
        self.client.cookies[settings.SESSION_COOKIE_NAME] = "invalid-session"
        self.assertEqual(self.client.get(self.me_url).status_code, 401)
        self.assertEqual(self.login().status_code, 200)
        Session.objects.filter(session_key=self.client.session.session_key).update(
            expire_date=timezone.now() - timedelta(seconds=1)
        )
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Authentication required."})
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_existing_session_loses_access_after_deactivation(self):
        self.login()
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self.client.get(self.me_url).status_code, 401)

    def test_login_rotates_session_and_csrf_secret(self):
        session = self.client.session
        session["anonymous_marker"] = True
        session.save()
        old_key = session.session_key
        old_csrf = self.client.cookies[settings.CSRF_COOKIE_NAME].value
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(self.client.session.session_key, old_key)
        self.assertFalse(Session.objects.filter(session_key=old_key).exists())
        self.assertNotEqual(self.client.cookies[settings.CSRF_COOKIE_NAME].value, old_csrf)
        self.assertEqual(self.client.post(self.logout_url, HTTP_X_CSRFTOKEN=self.token).status_code, 403)
        self.assertEqual(self.client.post(
            self.logout_url, HTTP_X_CSRFTOKEN=response.json()["csrf_token"]
        ).status_code, 204)

    def test_logout_flushes_server_session_and_replayed_cookie_is_rejected(self):
        response = self.login()
        key = self.client.session.session_key
        self.assertTrue(Session.objects.filter(session_key=key).exists())
        response = self.client.post(self.logout_url, HTTP_X_CSRFTOKEN=response.json()["csrf_token"])
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertEqual(response.cookies[settings.SESSION_COOKIE_NAME]["max-age"], 0)
        self.assertFalse(Session.objects.filter(session_key=key).exists())
        self.assertEqual(self.client.get(self.me_url).status_code, 401)
        replay = APIClient(enforce_csrf_checks=True)
        replay.cookies[settings.SESSION_COOKIE_NAME] = key
        self.assertEqual(replay.get(self.me_url).status_code, 401)

    def test_login_csrf_requires_cookie_token_and_trusted_origin(self):
        payload = {"email": self.user.email, "password": self.password}
        cases = [{}, {"HTTP_X_CSRFTOKEN": "invalid"},
                 {"HTTP_X_CSRFTOKEN": self.token, "HTTP_ORIGIN": "https://untrusted.example"}]
        for headers in cases:
            response = self.client.post(self.login_url, payload, format="json", **headers)
            self.assertEqual(response.status_code, 403)
            self.assertNotIn("_auth_user_id", self.client.session)
            self.assertIn("no-store", response.headers["Cache-Control"])
        no_cookie = APIClient(enforce_csrf_checks=True)
        self.assertEqual(no_cookie.post(self.login_url, payload, format="json",
                                       HTTP_X_CSRFTOKEN=self.token).status_code, 403)
        response = self.client.post(self.login_url, payload, format="json",
                                    HTTP_X_CSRFTOKEN=self.token, HTTP_ORIGIN="http://127.0.0.1:5173")
        self.assertEqual(response.status_code, 200)

    def test_logout_csrf_failure_does_not_end_session(self):
        token = self.login().json()["csrf_token"]
        for headers in ({}, {"HTTP_X_CSRFTOKEN": "invalid"},
                        {"HTTP_X_CSRFTOKEN": token, "HTTP_ORIGIN": "https://untrusted.example"}):
            self.assertEqual(self.client.post(self.logout_url, **headers).status_code, 403)
            self.assertEqual(self.client.get(self.me_url).status_code, 200)

    def test_anonymous_logout_is_idempotent_but_requires_csrf(self):
        self.assertEqual(self.client.post(self.logout_url).status_code, 403)
        for _ in range(2):
            self.assertEqual(self.client.post(self.logout_url, HTTP_X_CSRFTOKEN=self.token).status_code, 204)

    def test_get_logout_cannot_end_session_and_methods_are_restricted(self):
        token = self.login().json()["csrf_token"]
        self.assertEqual(self.client.get(self.logout_url).status_code, 405)
        self.assertEqual(self.client.get(self.me_url).status_code, 200)
        for url, method in ((self.login_url, "put"), (self.logout_url, "delete"), (self.me_url, "post")):
            self.assertEqual(getattr(self.client, method)(url, HTTP_X_CSRFTOKEN=token).status_code, 405)

    def test_login_configuration_sets_csrf_without_authenticating(self):
        response = self.client.get(self.login_url)
        self.assertEqual(set(response.json()), {"csrf_token"})
        self.assertIn(settings.CSRF_COOKIE_NAME, response.cookies)
        self.assertNotIn(settings.SESSION_COOKIE_NAME, response.cookies)
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_login_rejects_username_extra_fields_and_malformed_input(self):
        for payload in ({"username": self.user.email, "password": self.password},
                        {"email": self.user.email, "password": self.password, "is_staff": True},
                        {}, [], None, {"email": 42, "password": self.password},
                        {"email": self.user.email, "password": "x" * 129},
                        {"email": self.user.email, "password": None}):
            response = self.client.post(self.login_url, json.dumps(payload), content_type="application/json",
                                        HTTP_X_CSRFTOKEN=self.token)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json(), {"detail": "Invalid email or password."})
        response = self.client.post(self.login_url, '{"email":', content_type="application/json",
                                    HTTP_X_CSRFTOKEN=self.token)
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_database_error_has_generic_response(self):
        with patch("accounts.views.authenticate", side_effect=OperationalError("private database details")):
            response = self.login()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": "Sign-in is temporarily unavailable. Please try again."})
