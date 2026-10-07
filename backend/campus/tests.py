from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from .models import Block, Entrance, Room


class CampusSeedTests(TestCase):
    def seed(self):
        call_command("seed_campus", stdout=StringIO())

    def test_seed_is_repeatable_and_keeps_manual_edits(self):
        self.seed()
        Room.objects.filter(code="D117").update(description="Team correction")
        self.seed()
        self.assertEqual(Block.objects.count(), 6)
        self.assertEqual(Entrance.objects.count(), 3)
        self.assertEqual(Room.objects.count(), 128)
        self.assertEqual(Room.objects.get(code="D117").description, "Team correction")

    def test_barrels_and_recommendations(self):
        self.seed()
        room = Room.objects.get(code="E221")
        self.assertEqual(room.name, "Бочка D2")
        self.assertEqual(room.floor, 2)
        self.assertEqual(room.block.code, "E")
        self.assertEqual(room.effective_entrance.code, "MAIN")
        self.assertEqual(Block.objects.get(code="H").recommended_entrance.code, "G")
        self.assertEqual(Block.objects.get(code="H").recommendation_status, "USER_REPORTED")
        self.assertEqual(Block.objects.get(code="G").recommendation_status, "PROVISIONAL")

    def test_provisional_room_ranges_do_not_classify_staff(self):
        self.seed()
        self.assertEqual(Room.objects.get(code="I105").kind, Room.Kind.CLASSROOM)
        self.assertEqual(Room.objects.get(code="G105").floor, 1)
        self.assertEqual(Room.objects.get(code="I405").kind, Room.Kind.UNKNOWN)
        self.assertFalse(Room.objects.filter(code="I106").exists())
        self.assertFalse(Room.objects.filter(code="I02").exists())
        self.assertIn("Сгенерировано", Room.objects.get(code="I105").source)
        room = Room(code="I406", block=Block.objects.get(code="I"), floor=4)
        room.save()
        self.assertEqual(room.kind, Room.Kind.UNKNOWN)

    def test_h_recommendation_updates_previous_seed_but_keeps_manual_override(self):
        self.seed()
        block = Block.objects.get(code="H")
        block.recommended_entrance = None
        block.recommendation_status = "UNKNOWN"
        block.recommendation_note = "Для H сравнить входы G и I после сбора плана и расстояний."
        block.save()
        self.seed()
        block.refresh_from_db()
        self.assertEqual(block.recommended_entrance.code, "G")
        block.recommended_entrance = Entrance.objects.get(code="I")
        block.recommendation_note = "Manual surveyed route"
        block.save()
        self.seed()
        block.refresh_from_db()
        self.assertEqual(block.recommended_entrance.code, "I")

    def test_rejects_code_floor_and_block_mismatch(self):
        self.seed()
        for code, block, floor in [("I101", "I", 2), ("I101", "G", 1), ("I501", "I", 5)]:
            with self.subTest(code=code, block=block, floor=floor):
                with self.assertRaises(ValidationError):
                    Room(code=code, block=Block.objects.get(code=block), floor=floor).save()
