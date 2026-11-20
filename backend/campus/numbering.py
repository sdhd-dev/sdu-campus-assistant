"""Room numbering describes a location, never proves that a room exists."""
import re


def normalize_room_code(value):
    return value.strip().upper().translate(str.maketrans({"Е": "E", "І": "I"}))


def parse_room_code(value):
    code = normalize_room_code(value)
    match = re.fullmatch(r"([D-I])(0[0-9]|[1-4][0-9]{2})", code)
    if not match:
        raise ValueError("Use a block D–I and a room number, e.g. I02 or E204 (floors 0–4).")
    return code, match.group(1), int(match.group(2)[0])
