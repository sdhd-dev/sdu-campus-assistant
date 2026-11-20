import unittest

from .numbering import parse_room_code


class RoomNumberingTests(unittest.TestCase):
    def test_basement_and_floors(self):
        for code, expected in [("i02", ("I02", "I", 0)), (" I101 ", ("I101", "I", 1)),
                               ("E204", ("E204", "E", 2)), ("G305", ("G305", "G", 3)),
                               ("I405", ("I405", "I", 4)), ("Е221", ("E221", "E", 2))]:
            with self.subTest(code=code):
                self.assertEqual(parse_room_code(code), expected)

    def test_invalid_codes(self):
        for code in ["A101", "J101", "I501", "I2", "I10", "I1000", "I-101", ""]:
            with self.subTest(code=code):
                with self.assertRaises(ValueError):
                    parse_room_code(code)
