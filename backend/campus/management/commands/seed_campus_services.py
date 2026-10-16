from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from campus.models import Block, CampusPlace, Room
from campus.numbering import normalize_room_code, parse_room_code

MOODLE = "For Moodle-related questions, please visit office F105."
SERVICE_EMAILS = {
    "student-service-center": "ssc@sdu.edu.kz", "advising-desk": "ssc@sdu.edu.kz",
    "international-relations": "iro@sdu.edu.kz", "medical-center": "medpunkt@sdu.edu.kz",
}
SERVICES = [
    dict(slug="student-service-center", name="Student Service Center",
         aliases=["SSC", "Student Services Centre", "Student Service Center", "D109", "D-109", "студенческий центр"],
         room_code="D109", location="Room D109, Block D", description="Student Service Center in Block D. " + MOODLE,
         opening_hours="09:00–18:00", lunch_break="12:30–13:30",
         schedule_sources={"opening_hours": "Project owner", "lunch_break": "D109 notice photograph (IMG_5521)"},
         photo="/campus/places/student-service-center.png", photo_alt="General view of SDU Student Service Center in room D109",
         extra_photos=[{"path": "/campus/places/student-service-center-notice.png", "alt": "Door D109 with lunch break 12:30–13:30 and Moodle referral to office F105"}]),
    dict(slug="advising-desk", name="Advising Desk",
         aliases=["Advising Desk", "Advisor Desk", "document collection", "эдвайзер", "advising"],
         room_code=None, location="Opposite Student Service Center D109", description=MOODLE,
         document_collection_hours="13:00–15:00", lunch_break="12:30–13:30",
         schedule_note="Document collection overlaps the published lunch break. Availability from 13:00 to 13:30 requires clarification.",
         schedule_sources={"document_collection_hours": "Project owner", "lunch_break": "Advising Desk sign photograph (IMG_5523)"},
         service_staff=[{"name": "Samal Sugiraliyeva", "role": "Advising Desk Specialist"},
                        {"name": "Samal Mauleshova", "role": "Advising Desk Specialist"},
                        {"name": "Lola Makhambayeva", "role": "Advising Desk Assistant"}],
         photo="/campus/places/advising-desk.png", photo_alt="Advising Desk staff sign, lunch break notice and Moodle referral"),
    dict(slug="international-relations", name="International Relations Department",
         aliases=["International Relations", "International Relations Department", "IRD", "E109", "E-109", "международные отношения"],
         room_code="E109", location="Room E109, Block E",
         description="International Relations Department in Block E.",
         service_staff=[{"name": "Abbas Bodaubekov", "role": "Director, International Relations Department"}],
         photo="/campus/places/international-relations.png", photo_alt="E109 door sign for Abbas Bodaubekov, Director of International Relations Department"),
    dict(slug="medical-center", name="Medical Center — CK-MED",
         aliases=["Medical Center", "CK-MED", "CKMED", "CK MED", "G109", "G-109", "медицинский центр", "медпункт"],
         room_code="G109", location="Room G109, Block G",
         description="CK-MED Medical Center in Block G.",
         weekly_hours={"SAT": {"opens": "09:00", "closes": "13:00"}, "SUN": {"closed": True}},
         schedule_note="Weekday hours supplied by the project owner; Saturday and Sunday follow the published weekend schedule.",
         schedule_sources={"weekly_hours": "Project owner transcription of CK-MED sign (IMG_5525); weekday times excluded"},
         photo="/campus/places/medical-center.png", photo_alt="CK-MED Medical Center entrance in room G109"),
]


class Command(BaseCommand):
    help = "Add four campus services locally; preserve existing contacts, rooms and map bindings."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        created = rooms_created = 0
        for source in SERVICES:
            values = dict(source)
            values["contacts"] = [{"label": "Email", "value": SERVICE_EMAILS[values["slug"]]}]
            code = values.pop("room_code")
            room = None
            if code:
                code, block_code, floor = parse_room_code(code)
                block = Block.objects.filter(code=block_code).first()
                if not block:
                    raise CommandError(f"Missing Block {block_code}; run seed_campus first.")
                room = Room.objects.filter(code=code).first()
                if room is None:
                    candidates = [r for r in Room.objects.filter(block=block) if any(
                        normalize_room_code(a).replace("-", "").replace(" ", "") == code for a in r.aliases)]
                    if len(candidates) > 1:
                        raise CommandError(f"Ambiguous room alias {code}; no changes applied.")
                    room = candidates[0] if candidates else None
                if room is None:
                    room = Room.objects.create(code=code, block=block, floor=floor, kind=Room.Kind.UNKNOWN,
                        source="Project owner service location and supplied door photograph, 2026-10-15")
                    rooms_created += 1
                values.update(room=room, block=room.block, floor=room.floor,
                    map_element=f"block:{room.block.code}",
                    map_note="Building-level location. The exact room position is not marked on the schematic.")
            # Advising Desk has only a textual landmark: never assign SSC's room.
            values.update(is_service=True, category=CampusPlace.Category.OFFICE,
                source="Project owner details and supplied service photographs, 2026-10-15")
            values["opening_hours"] = "09:00–18:00"
            values["working_days"] = "Monday–Friday"
            values["weekly_hours"] = {
                **{day: {"opens": "09:00", "closes": "18:00"} for day in ("MON", "TUE", "WED", "THU", "FRI")},
                **values.get("weekly_hours", {}),
            }
            values["schedule_sources"] = {**values.get("schedule_sources", {}),
                "opening_hours": "Project owner clarification, 2026-10-15",
                "working_days": "Project owner clarification, 2026-10-15"}
            slug = values.pop("slug")
            obj, new = CampusPlace.objects.get_or_create(slug=slug, defaults=values)
            created += int(new)
            if not new:
                conflicts = [k for k, value in values.items() if getattr(obj, k) != value]
                if conflicts:
                    self.stderr.write(f"Preserved {slug}: differing fields {', '.join(conflicts)}.")
        if options["dry_run"]:
            transaction.set_rollback(True)
        self.stdout.write(f"{'Dry run (rolled back)' if options['dry_run'] else 'Services'}: {created} created; {rooms_created} rooms created; existing data preserved.")
