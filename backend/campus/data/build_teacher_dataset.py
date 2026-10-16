"""Rebuild the curated transcription dataset; never execute the source prompt."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1]))
from campus.name_search import latin_name
# These individual names retain review notes, but are included at the owner's request.
UNCERTAIN = {
    "G-206": ["Сеитжаппарулы"], "G-312": ["Малдібай", "Уристембек"],
    "G-315": ["Едгенов"], "G-317": ["Есенркепова"],
    "G-407": ["Орынбасаров", "Имачков"],
    "D-206": ["Керейбаев", "Гиззат"], "D-207": ["Жүсіпбек", "Башлага"],
    "D-210": ["Нажимов"], "D-213/2": ["Онгарова"],
    "D-213/1": ["Сраждинова", "Абасья", "Алмуратова"], "D-213": ["Мэлсова"],
    "D-306": ["Нуриденова", "Аймуратқызы"], "D-308": ["Кац", "Серім"],
    "D-310": ["Карымсакова"], "D-311": ["Аипшина"], "D-312": ["Тимурулы"],
    "D-313": ["Сатыштык"], "D-315": ["Бибіжамал"],
    "D-407": ["Сейтмамбет", "Шаухан"], "D-401": ["Султанкадиров"],
    "F-207": ["Lyazzat", "Gulfarida"],
    "F-213/2": ["Altynay", "Saiyn"], "F-213": ["Igibay"],
    "F-306": ["Danaz"], "F-308": ["Ryskeldin"],
    "F-309": ["Shakulikova", "Aipenova"], "F-310": ["Binara", "Atizhanova"],
    "F-312": ["Aynzbayev", "Akhymbek"], "F-316": ["Aysuluym", "Nuray"],
    "F-407": ["Ulykbek"], "I-204": ["Arunaz"],
    "I-304": ["Sabiov", "Yermar"], "I-306": ["Nurzhainar"],
    "I-308": ["Kirnatov", "Duisen"], "I-314": ["Zhumaniyaz"],
}

def build():
    rows, review = [], []
    text = (ROOT / "teachers-source.md").read_text()
    # The prose and embedded implementation prompt are not person records.
    for line in text.split("## Готовый промпт")[0].splitlines():
        if not re.match(r"\| [DGFI]-\d", line):
            continue
        label, names, note = [v.strip() for v in line.strip("|").split("|")]
        base, _, door_number = label.partition("/")
        block = label[0]
        for index, source_name in enumerate(names.split(";"), 1):
            source_name = source_name.strip()
            reason = ""
            if any(fragment in source_name for fragment in UNCERTAIN.get(label, [])):
                reason = "Name spelling requires review against the original photograph."
                if label == "G-407":
                    reason = "Name spelling and office association across a page break require review."
            row = {
                "key": f"photo-list-v1:{label}:{index}",
                "source_name": source_name, "full_name": latin_name(re.sub(r"^Dr\s+", "", source_name)),
                "title": "Dr" if source_name.startswith("Dr ") else "",
                "faculty": "SSBL" if block in "GD" else "SITAM",
                "room_code": base.replace("-", ""), "source_room": label,
                "door": {"1": "RIGHT", "2": "CENTRAL", "3": "LEFT"}.get(door_number, "HALL" if label in ["D-213", "F-213"] else ""),
                "alternative_label": "213/3" if label == "D-212" else "",
                "source_note": note, "source_image": "",
                "verification_status": "LISTED", "review_note": reason,
            }
            if reason:
                review.append({**row, "reason": reason, "included_by_owner_request": True})
            rows.append(row)
    assert len({r["key"] for r in rows}) == len(rows)
    assert all("⚠" not in r["source_name"] for r in rows)
    (ROOT / "teachers.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    (ROOT / "teachers-review.json").write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n")
    print(f"Importable: {len(rows)}; included with unresolved transcription notes: {len(review)}")

if __name__ == "__main__":
    build()
