"""Team-approved content, shared by fresh seed and conservative data updates."""
from django.db import transaction

from .models import Block, Room

FACULTY_SOURCE = 'Team-provided campus diagram; not independently verified'
FACULTIES = {
    'D': 'Faculty of Law & Social Sciences',
    'E': 'Faculty of Education & Humanities',
    'F': 'Faculty of Engineering and Natural Sciences',
    'G': 'SDU Business School',
}
# Legacy values are an explicit allowlist, not a heuristic for overwriting edits.
BARREL_DETAILS = [
    ('D117', 'A1', '1-й этаж, первая от главного входа',
     'First floor. The first barrel hall when entering through the main entrance.'),
    ('D218', 'A2', '2-й этаж, первая от главного входа',
     'Second floor. The first barrel hall when entering through the main entrance.'),
    ('D116', 'B1', '1-й этаж, вторая от главного входа',
     'First floor. The second barrel hall when entering through the main entrance.'),
    ('D217', 'B2', '2-й этаж, вторая от главного входа',
     'Second floor. The second barrel hall when entering through the main entrance.'),
    ('D113', 'C1', '1-й этаж, третья, рядом с Advisor Desk',
     'First floor. The third barrel hall when entering through the main entrance, near the Advisor Desk.'),
    ('D214', 'C2', '2-й этаж, третья, рядом с Advisor Desk',
     'Second floor. The third barrel hall when entering through the main entrance, near the Advisor Desk.'),
    ('E117', 'D1', '1-й этаж, четвёртая, рядом с Red Canteen',
     'First floor. The fourth barrel hall when entering through the main entrance, near the Red Canteen.'),
    ('E221', 'D2', '2-й этаж, четвёртая, рядом с Red Canteen',
     'Second floor. The fourth barrel hall when entering through the main entrance, near the Red Canteen.'),
]


@transaction.atomic
def update_approved_details(stdout, stderr):
    updated_rooms = updated_blocks = conflicts = 0

    def warn(message):
        nonlocal conflicts
        conflicts += 1
        stderr.write(f'Conflict: {message}. Existing value preserved.')

    for code, alias, legacy_description, description in BARREL_DETAILS:
        room = Room.objects.select_for_update().filter(code=code).first()
        if room is None:
            stderr.write(f'Missing room {code}; no record created. Run seed_campus if needed.')
            continue
        changes = {}
        for field, legacy, approved in [('name', f'Бочка {alias}', f'Barrel {alias}'),
                                        ('description', legacy_description, description)]:
            current = getattr(room, field)
            if current == approved:
                continue
            if current in ('', legacy):
                changes[field] = approved
            else:
                warn(f'{code}.{field} differs from the old seed and approved text')
        if changes:
            # Only text fields change; code, block, floor, aliases and entrance stay intact.
            Room.objects.filter(pk=room.pk).update(**changes)
            updated_rooms += 1
    for code, faculty in FACULTIES.items():
        block = Block.objects.select_for_update().filter(code=code).first()
        if block is None:
            stderr.write(f'Missing block {code}; no record created.')
            continue
        if block.faculty_name not in ('', faculty):
            warn(f'Block {code}.faculty_name has a manual correction')
            continue
        if block.faculty_source not in ('', FACULTY_SOURCE):
            warn(f'Block {code}.faculty_source has manual provenance')
            continue
        changes = {}
        if block.faculty_name != faculty:
            changes['faculty_name'] = faculty
        if block.faculty_source != FACULTY_SOURCE:
            changes['faculty_source'] = FACULTY_SOURCE
        if changes:
            Block.objects.filter(pk=block.pk).update(**changes)
            updated_blocks += 1
    stdout.write(f'Campus details updated: {updated_rooms} rooms, {updated_blocks} blocks; {conflicts} conflicts.')
