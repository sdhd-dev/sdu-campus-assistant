from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase
from django.urls import reverse


class HealthTests(TestCase):
    def test_health_is_public_and_checks_postgresql(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_database_outage_returns_generic_error(self):
        with patch("core.views.connection.cursor", side_effect=OperationalError("sensitive database details")):
            response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})
        self.assertNotContains(response, "sensitive", status_code=503)

    def test_health_does_not_accept_writes(self):
        self.assertEqual(self.client.post(reverse("health"), {}).status_code, 405)
