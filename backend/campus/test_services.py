from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import DatabaseError
from django.test import TestCase
from rest_framework.test import APIClient

from .models import CampusPlace, Room


class ServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_campus", stdout=StringIO())
        call_command("seed_campus_places", stdout=StringIO())
        call_command("seed_campus_services", stdout=StringIO())
        cls.user = get_user_model().objects.create_user(email="services-test@example.com", password="Service-test-472!")

    def setUp(self):
        self.client = APIClient()
        self.client.force_login(self.user)

    def detail(self, slug):
        response = self.client.get("/api/campus/services/", {"slug": slug})
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_service_list_and_unknown_fields(self):
        response = self.client.get("/api/campus/services/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["services"]), 4)
        for item in response.data["services"]:
            self.assertTrue(item["is_service"])
            expected_email = {"student-service-center":"ssc@sdu.edu.kz", "advising-desk":"ssc@sdu.edu.kz",
                              "international-relations":"iro@sdu.edu.kz", "medical-center":"medpunkt@sdu.edu.kz"}[item["code"]]
            self.assertEqual(item["contacts"], [{"label":"Email", "value":expected_email}])
            self.assertEqual(item["working_days"], "Monday–Friday")
            self.assertNotIn("open_now", item)
        ir = self.detail("international-relations")
        self.assertEqual((ir["room_code"], ir["block"]["code"], ir["floor"]), ("E109", "E", 1))
        self.assertEqual(ir["opening_hours"], "09:00–18:00")
        self.assertEqual(ir["service_staff"], [{"name":"Abbas Bodaubekov","role":"Director, International Relations Department"}])

    def test_ssc_hours_lunch_moodle_and_photo_order(self):
        item = self.detail("student-service-center")
        self.assertEqual((item["room_code"], item["floor"]), ("D109", 1))
        self.assertEqual(item["opening_hours"], "09:00–18:00")
        self.assertEqual(item["lunch_break"], "12:30–13:30")
        self.assertEqual(item["document_collection_hours"], "")
        self.assertEqual(item["photo"], "/campus/places/student-service-center.png")
        self.assertEqual(item["extra_photos"][0]["path"], "/campus/places/student-service-center-notice.png")
        self.assertIn("office F105", item["description"])
        self.assertNotEqual(item["room_code"], "F105")

    def test_advising_landmark_overlap_and_staff_are_not_contacts(self):
        item = self.detail("advising-desk")
        self.assertIsNone(item["room_code"])
        self.assertIsNone(item["floor"])
        self.assertIsNone(item["block"])
        self.assertFalse(item["map_available"])
        self.assertIn("Opposite", item["location"])
        self.assertEqual(item["opening_hours"], "09:00–18:00")
        self.assertEqual(item["document_collection_hours"], "13:00–15:00")
        self.assertEqual(item["lunch_break"], "12:30–13:30")
        self.assertIn("13:00 to 13:30", item["schedule_note"])
        self.assertEqual(len(item["service_staff"]), 3)
        self.assertEqual(item["contacts"], [{"label":"Email", "value":"ssc@sdu.edu.kz"}])

    def test_medical_weekends_without_guessed_weekday_times(self):
        item = self.detail("medical-center")
        self.assertEqual(item["room_code"], "G109")
        self.assertEqual(item["weekly_hours"]["SAT"], {"opens":"09:00","closes":"13:00"})
        self.assertEqual(item["weekly_hours"]["SUN"], {"closed":True})
        self.assertEqual(item["opening_hours"], "09:00–18:00")
        for day in ("MON","TUE","WED","THU","FRI"):
            self.assertEqual(item["weekly_hours"][day], {"opens":"09:00","closes":"18:00"})
        self.assertIn("project owner", item["schedule_note"])

    def test_search_by_service_and_normalized_room_code(self):
        for query, slug in [("SSC","student-service-center"), ("D-109","student-service-center"),
                            ("E109","international-relations"), ("CK-MED","medical-center"),
                            ("G109","medical-center"), ("Advising Desk","advising-desk")]:
            results = self.client.get("/api/campus/search/", {"q":query}).data["results"]
            self.assertIn(slug, [r["code"] for r in results if r["type"]=="place"])
        self.assertFalse(any(r["type"]=="place" for r in self.client.get("/api/campus/search/", {"q":"F105"}).data["results"]))

    def test_map_link_uses_confirmed_block_and_unmapped_landmark(self):
        for slug, code in [("student-service-center","D"), ("international-relations","E"), ("medical-center","G")]:
            item = self.detail(slug)
            response = self.client.get("/api/campus/location/", {"type":"place","id":item["id"]})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["map"]["block_code"], code)
            self.assertEqual(response.data["room_code"], code+"109")
        item = self.detail("advising-desk")
        response = self.client.get("/api/campus/location/", {"type":"place","id":item["id"]})
        self.assertIsNone(response.data["map"]["block_code"])
        self.assertIn("D109", response.data["location"])

    def test_seed_preserves_contacts_existing_e109_landmarks_and_room_data(self):
        service = CampusPlace.objects.get(slug="student-service-center")
        service.contacts = [{"label":"Published email (test fixture)", "value":"test@example.com"}]
        service.opening_hours = "Manual confirmed hours"
        service.save()
        room = Room.objects.get(code="E109")
        room.description = "Existing room landmark data"
        room.aliases = ["E-109"]
        room.save()
        other = CampusPlace.objects.create(slug="existing-e109-landmark", name="Existing landmark", category="OTHER",
            room=room, map_element="block:E")
        before = (Room.objects.count(), CampusPlace.objects.count())
        call_command("seed_campus_services", stdout=StringIO(), stderr=StringIO())
        service.refresh_from_db(); room.refresh_from_db(); other.refresh_from_db()
        self.assertEqual((Room.objects.count(), CampusPlace.objects.count()), before)
        self.assertEqual(service.contacts[0]["value"], "test@example.com")
        self.assertEqual(service.opening_hours, "Manual confirmed hours")
        self.assertEqual(room.description, "Existing room landmark data")
        self.assertEqual(other.room_id, room.pk)
        self.assertEqual(other.map_element, "block:E")

    def test_dry_run_no_duplicate_rooms(self):
        CampusPlace.objects.filter(is_service=True).delete()
        before = (Room.objects.count(), CampusPlace.objects.count())
        call_command("seed_campus_services", dry_run=True, stdout=StringIO())
        self.assertEqual((Room.objects.count(), CampusPlace.objects.count()), before)
        self.assertFalse(CampusPlace.objects.filter(is_service=True).exists())

    def test_photos_are_permanent_real_project_files(self):
        public = Path(__file__).resolve().parents[2] / "frontend" / "public"
        for place in CampusPlace.objects.filter(is_service=True):
            photos = [{"path":place.photo,"alt":place.photo_alt}] + place.extra_photos
            for photo in photos:
                self.assertTrue((public / photo["path"].lstrip("/")).is_file(), photo)
                self.assertTrue(photo["alt"])

    def test_invalid_schedule_or_external_photos_rejected(self):
        place = CampusPlace.objects.get(slug="medical-center")
        for invalid in [{"MON":{"opens":"25:00","closes":"26:00"}}, {"FUNDAY":{"closed":True}}, {"SAT":{"opens":"13:00","closes":"09:00"}}]:
            place.weekly_hours = invalid
            with self.assertRaises(ValidationError):
                place.full_clean()
        place.refresh_from_db()
        place.extra_photos = [{"path":"https://example.com/not-local.png","alt":"Bad path"}]
        with self.assertRaises(ValidationError):
            place.full_clean()

    def test_access_and_retryable_failure(self):
        self.assertEqual(self.client.get("/api/campus/services/", {"slug":"missing"}).status_code,404)
        with patch("campus.service_views.places_queryset", side_effect=DatabaseError):
            self.assertEqual(self.client.get("/api/campus/services/").status_code,503)
        self.client.logout()
        self.assertEqual(self.client.get("/api/campus/services/").status_code,401)
