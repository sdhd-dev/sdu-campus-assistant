import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from campus.models import Block, DirectoryFaculty, OfficeAssignment, Person, Room
from campus.numbering import normalize_room_code, parse_room_code

DATA = Path(__file__).resolve().parents[2] / "data" / "teachers.json"
FACULTIES = {"SSBL": "School of Social Sciences, Business and Law", "SITAM": "SITAM (School of IT and Applied Mathematics)"}
FACULTY_BLOCKS = {"SSBL": {"D", "G"}, "SITAM": {"F", "I"}}


class Command(BaseCommand):
    help = "Import the owner-approved complete office list; preserve source notes and existing manual data."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        rows = json.loads(DATA.read_text())
        counts = {"people": 0, "offices": 0, "rooms": 0, "preserved": 0}
        # Preflight the complete dataset before writing anything.
        for row in rows:
            if row["verification_status"] != "LISTED" or row["faculty"] not in FACULTIES:
                raise CommandError("Only curated LISTED records may be imported.")
            _, block, _ = parse_room_code(row["room_code"])
            if block not in FACULTY_BLOCKS[row["faculty"]]:
                raise CommandError("The source faculty/block mapping is inconsistent.")
            if not Block.objects.filter(code=block).exists():
                raise CommandError(f"Missing Block {block}; run seed_campus first.")
        for row in rows:
            faculty, _ = DirectoryFaculty.objects.get_or_create(
                code=row["faculty"], defaults={"name": FACULTIES[row["faculty"]]})
            code, block_code, floor = parse_room_code(row["room_code"])
            # Match a pre-existing normalized alias before adding room inventory.
            room = Room.objects.filter(code=code).first()
            if room is None:
                candidates = []
                for candidate in Room.objects.filter(block__code=block_code):
                    if any(normalize_room_code(a).replace("-", "").replace(" ", "") == code for a in candidate.aliases):
                        candidates.append(candidate)
                if len(candidates) > 1:
                    raise CommandError(f"Ambiguous existing room aliases for {code}; review before import.")
                room = candidates[0] if candidates else None
            if room is None:
                room = Room.objects.create(code=code, block=Block.objects.get(code=block_code),
                    floor=floor, kind=Room.Kind.STAFF_OFFICE,
                    source="Office transcription: current allocation unverified")
                counts["rooms"] += 1
            person, created = Person.objects.get_or_create(source_key=row["key"], defaults={
                "full_name": row["full_name"], "source_name": row["source_name"],
                "title": row["title"], "source_image": row["source_image"],
                "source": "teachers_campus_assistant.md; transcription of image(4).png, image(5).png, image(6).png; per-record image not identified",
                "verification_status": Person.Verification.LISTED,
                "note": "Teacher role assigned at project owner's request." + (" Transcription review: " + row["review_note"] if row.get("review_note") else ""),
            })
            counts["people"] += int(created)
            counts["preserved"] += int(not created)
            _, created = OfficeAssignment.objects.get_or_create(source_key=row["key"] + ":office", defaults={
                "person": person, "faculty": faculty, "room": room,
                "source_room": row["source_room"], "door": row["door"],
                "alternative_label": row["alternative_label"],
                "note": "Office listed in the source; current allocation and presence are not confirmed.",
            })
            counts["offices"] += int(created)
        if options["dry_run"]:
            transaction.set_rollback(True)
        self.stdout.write(("DRY RUN (rolled back): " if options["dry_run"] else "Imported: ") + str(counts))
