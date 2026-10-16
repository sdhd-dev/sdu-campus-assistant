"""Deterministic display transliteration and cross-script search keys.

This is a presentation/search convention, not an official passport spelling.
Original source names remain unchanged.
"""
import re
import unicodedata

LETTERS = dict(zip(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюяәғқңөұүһі",
    ["a", "b", "v", "g", "d", "e", "yo", "zh", "z", "i", "y", "k", "l",
     "m", "n", "o", "p", "r", "s", "t", "u", "f", "kh", "ts", "ch", "sh",
     "shch", "", "y", "", "e", "yu", "ya", "a", "gh", "q", "ng", "o", "u", "u", "h", "i"],
    strict=True,
))


def normalize_name(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def latin_name(value):
    result = []
    for letter in unicodedata.normalize("NFC", value):
        replacement = LETTERS.get(letter.casefold())
        result.append(letter if replacement is None else replacement.capitalize() if letter.isupper() else replacement)
    return "".join(result)


def latin_search_key(value):
    value = normalize_name(latin_name(value))
    # Allow common cross-script spelling differences (Aleksei/Aleksey,
    # Q/K and Kh/H) without merging person identities.
    for source, replacement in [("shch", "sh"), ("kh", "h"), ("gh", "g"), ("zh", "j"), ("q", "k"), ("y", "i"), ("w", "v")]:
        value = value.replace(source, replacement)
    return re.sub(r"[^a-z0-9\s]", "", value).strip()
