# Campus data foundation (Stories 6–7)

This supplies the prepared database foundation. Story 6 adds the session-protected
search API and frontend; see [room-building-search.md](room-building-search.md).
Source: information supplied by the project team on 2026-10-07, not an official inventory.

## Load into your project PostgreSQL database

From the repository root, with the existing `.env` and virtual environment:

```sh
python backend/manage.py check
python backend/manage.py migrate
python backend/manage.py seed_campus
python backend/manage.py test campus --keepdb
```

The command is atomic and repeatable. It creates six blocks D–I, three entrances
and the eight reported barrel rooms plus 120 provisional ordinary room records. Existing records and manual corrections are
preserved. No production database has been accessed as part of preparing this change.

## Data model

- Block: code, name, horizontal order, recommended entrance, recommendation status/note.
- Entrance: MAIN/G/I, name, optional associated block, description.
- Room: unique code, block, floor (0 = basement), kind, name, aliases, description,
  source, optional room-specific entrance override.
- `Room.effective_entrance` resolves the room override, then the block recommendation.

The order D–I is schematic, not coordinates or measured walking distances.
No invented map coordinates are stored. Add them once a campus plan is available.

## Numbering and inventory

I02 means basement, I101 means floor 1, and the first digit of three-digit room
numbers identifies floors 1–4. This parser does not prove that a room exists.
At the team’s request, seed_campus generates rooms 101–105, 201–205, 301–305
and 401–405 for every block D–I (120 provisional records). Their source and
description clearly mark them as generated, pending inventory verification.
Floors 1–3 default to CLASSROOM; floor 4 remains UNKNOWN because it usually
contains staff offices. Basement numbering is supported but basement rooms are
not generated: no basement inventory range was supplied. Numbers above 05 are
not generated, apart from the eight separately reported barrel rooms.

Fourth-floor rooms and numbers ending above 5 were described as *usually* staff
offices. They are not auto-classified; the default kind is UNKNOWN. Staff names
and office assignments need a separately collected directory.

## Initial rooms

| Code | Name | Floor | Description |
| --- | --- | --- | --- |
| D117 | Бочка A1 | 1 | первая от главного входа |
| D218 | Бочка A2 | 2 | первая от главного входа |
| D116 | Бочка B1 | 1 | вторая от главного входа |
| D217 | Бочка B2 | 2 | вторая от главного входа |
| D113 | Бочка C1 | 1 | третья, рядом с Advisor Desk |
| D214 | Бочка C2 | 2 | третья, рядом с Advisor Desk |
| E117 | Бочка D1 | 1 | четвёртая, рядом с Red Canteen |
| E221 | Бочка D2 | 2 | четвёртая, рядом с Red Canteen |

Aliases such as A1 and Бочка A1 are stored for future search. They are distinct
from the block letter: Бочка D2 is in block E, room E221.

## Entrance recommendations

| Blocks | Entrance | Status |
| --- | --- | --- |
| D, E, F | MAIN | USER_REPORTED |
| G | G | PROVISIONAL; verify walking path |
| I | I | PROVISIONAL; verify walking path |
| H | G | USER_REPORTED; team confirmed G is more convenient |

The UI should label provisional recommendations and never claim a shortest route.
No room existence or staff-office classification should be inferred by the frontend.

## Updating an earlier seed

Run migrate and seed_campus again. The command adds missing ordinary rooms and
updates the former untouched H recommendation to entrance G. Existing room edits
and manually changed entrance recommendations are preserved. No schema change
is required for this inventory update.
