from io import StringIO
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from rest_framework.test import APIClient

from .directory import matching_people, person_data
from .models import DirectoryFaculty, OfficeAssignment, Person, Room


class DirectoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_campus", stdout=StringIO())
        call_command("import_teachers", stdout=StringIO())
        cls.user = get_user_model().objects.create_user(email="directory@example.com", password="Directory-test-987!")

    def setUp(self):
        self.client = APIClient()
        self.client.force_login(self.user)

    def search(self, q, **params):
        response = self.client.get("/api/campus/search/", {"q": q, **params})
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_complete_dataset_includes_review_notes_without_claiming_verification(self):
        root = Path(__file__).parent / "data"
        included = json.loads((root / "teachers.json").read_text())
        held = json.loads((root / "teachers-review.json").read_text())
        self.assertEqual(Person.objects.count(), len(included))
        self.assertEqual(OfficeAssignment.objects.count(), len(included))
        self.assertEqual(len(included), 205)
        self.assertEqual(Person.objects.filter(source_key__in=[r["key"] for r in held]).count(), 52)
        self.assertTrue(Person.objects.filter(source_name="Гасанов Нури").exists())
        for row in held:
            p = Person.objects.get(source_key=row["key"])
            self.assertNotEqual(p.verification_status, "VERIFIED")
            self.assertIn(row["reason"], p.note)
        self.assertFalse(any(any("\u0400" <= c <= "\u04ff" for c in p.full_name) for p in Person.objects.all()))
        self.assertFalse(Person.objects.filter(full_name__in=["PED", "ped", "WE", "LAW Clinic"]).exists())

    def test_unicode_case_spacing_title_and_cross_script_search(self):
        for q in ["  aleksei   KAVOKIN ", "Aleksei"]:
            result = self.search(q)["results"][0]
            self.assertEqual(result["name"], "Aleksei Kavokin")
            self.assertEqual(result["offices"][0]["source_room"], "F-307")
        self.assertEqual(self.search("ғұмырзақ")["results"][0]["name"], "Ghumyrzaq Aqmaral")
        dr = self.search("raj kumar")["results"][0]
        self.assertEqual((dr["name"], dr["title"], dr["source_name"]), ("Raj Kumar", "Dr", "Dr Raj Kumar"))
        self.assertEqual(self.search("Алексей Кавокин")["results"][0]["name"], "Aleksei Kavokin")
        self.assertEqual(self.search("Сеитжаппарулы")["results"][0]["name"], "Seitzhapparuly Mukhametzhan")

    def test_shared_office_and_map_people(self):
        room = Room.objects.get(code="F307")
        self.assertEqual(self.search("f-307")["results"][0]["id"], room.pk)
        names = {x["name"] for x in self.search("F307")["results"][0]["people"]}
        self.assertEqual(names, {"Aleksei Kavokin", "Sufyan Mustafa"})
        location = self.client.get("/api/campus/location/", {"type": "room", "id": room.pk})
        self.assertEqual(location.status_code, 200)
        self.assertEqual(location.data["map"]["block_code"], "F")
        self.assertEqual({p["name"] for p in location.data["people"]}, names)

    def test_source_room_floor_door_and_ambiguous_alternate(self):
        office = self.search("Тулепбаев")["results"][0]["offices"][0]
        self.assertEqual(office["room"]["floor"], 2)
        office = self.search("Ramis Akhmedov")["results"][0]["offices"][0]
        self.assertEqual((office["source_room"], office["room"]["code"], office["door"]), ("F-213/3", "F213", "LEFT"))
        person = self.search("Сабденалиев")["results"][0]
        self.assertEqual(person["role"], "TEACHER")
        self.assertEqual(person["offices"][0]["alternative_label"], "213/3")
        self.assertEqual(person["offices"][0]["room"]["code"], "D212")

    def test_idempotence_preserves_manual_names_office_and_rooms(self):
        person = Person.objects.get(full_name="Aleksei Kavokin")
        person.full_name = "Manually checked spelling"
        person.save()
        office = person.offices.get()
        office.note = "Manually checked office"
        office.save()
        room = office.room
        room.description = "Manual room information"
        room.save()
        before = (Person.objects.count(), OfficeAssignment.objects.count(), Room.objects.count())
        call_command("import_teachers", stdout=StringIO())
        self.assertEqual(before, (Person.objects.count(), OfficeAssignment.objects.count(), Room.objects.count()))
        person.refresh_from_db(); office.refresh_from_db(); room.refresh_from_db()
        self.assertEqual(person.full_name, "Manually checked spelling")
        self.assertEqual(office.note, "Manually checked office")
        self.assertEqual(room.description, "Manual room information")
        self.assertEqual(self.search("manually checked spelling")["results"][0]["id"], person.pk)

    def test_dry_run_rolls_back_new_records(self):
        OfficeAssignment.objects.all().delete()
        Person.objects.all().delete()
        call_command("import_teachers", dry_run=True, stdout=StringIO())
        self.assertEqual(Person.objects.count(), 0)
        self.assertEqual(OfficeAssignment.objects.count(), 0)

    def test_faculty_filter_limits_people_not_other_rooms(self):
        self.assertEqual(self.search("E204", type="person")["count"], 0)
        self.assertEqual(self.search("Library", type="person")["count"], 0)
        self.assertEqual(self.search("Aleksei", type="person")["results"][0]["type"], "person")
        self.assertTrue(all(r["type"] == "person" for r in self.search("a", type="person")["results"]))
        self.assertEqual(self.search("Aleksei", faculty="SITAM")["count"], 1)
        self.assertEqual(self.search("Aleksei", faculty="SSBL")["count"], 0)
        self.assertEqual(self.search("E204", faculty="SITAM")["count"], 0)
        self.assertEqual(self.client.get("/api/campus/search/", {"q": "a", "faculty": "made-up"}).status_code, 400)

    def test_missing_map_room_and_review_hidden(self):
        p = Person.objects.get(full_name="Aleksei Kavokin")
        p.offices.update(room=None)
        result = self.search("Aleksei")["results"][0]
        self.assertFalse(result["map_available"])
        self.assertIsNone(result["offices"][0]["room"])
        p.verification_status = Person.Verification.REVIEW; p.save()
        self.assertEqual(self.search("Aleksei")["count"], 0)
        self.assertFalse(any(p["name"] == "Aleksei Kavokin" for p in self.search("F307")["results"][0]["people"]))

    def test_homonyms_and_multiple_offices_are_not_merged(self):
        p = Person.objects.get(full_name="Aleksei Kavokin")
        other = Person.objects.create(source_key="manual-homonym", full_name=p.full_name, source_name=p.full_name, source="Manual fixture")
        self.assertEqual(self.search("Aleksei Kavokin")["count"], 2)
        OfficeAssignment.objects.create(source_key="manual-other-office", person=p, faculty=DirectoryFaculty.objects.get(code="SSBL"),
            room=Room.objects.get(code="D201"), source_room="D-201")
        self.assertEqual(len(next(r for r in self.search("Aleksei")["results"] if r["id"] == p.pk)["offices"]), 2)
        self.assertNotEqual(p.pk, other.pk)

    def test_person_serialization_queries_are_batched(self):
        counts = []
        for size in (1, 30):
            with CaptureQueriesContext(connection) as context:
                [person_data(p) for p in matching_people("a")[:size]]
            counts.append(len(context))
        self.assertEqual(counts, [2, 2])

    def test_pagination_and_session_access(self):
        first = self.search("a", page_size=2)
        second = self.search("a", page_size=2, page=2)
        self.assertTrue(first["next_page"])
        key = lambda r: (r["type"], r["id"])
        self.assertFalse({key(r) for r in first["results"]} & {key(r) for r in second["results"]})
        self.client.logout()
        self.assertEqual(self.client.get("/api/campus/search/", {"q": "Aleksei"}).status_code, 401)
