# Approved barrel descriptions and faculty details

## Cause and correction

The existing PostgreSQL records had all eight descriptions, but they were the
legacy Russian seed values. `get_or_create(defaults=...)` did not update those
existing rows on a repeat seed. Both selection and search APIs already included
`description`; the map card never rendered it. Search could render descriptions,
but did not have the approved English content or faculty metadata.

Descriptions are now visible paragraphs through the shared `RoomDescription`
component in Search and Campus Map. It does not hide barrel/manual descriptions
when they happen to equal a recommendation note. The generated ordinary-room
placeholder remains omitted. `FacultyInfo` likewise renders the same backend block
metadata in both cards. Refresh and direct map links resolve the complete record.

## Update an existing project database

From the repository root, using its existing local `.env` and PostgreSQL cluster:

```sh
source .venv/bin/activate
python backend/manage.py migrate
python backend/manage.py update_campus_details
```

The schema migration adds only `Block.faculty_name` and `Block.faculty_source`.
The separate update command changes only the eight known rooms' name/description
and the four known blocks' faculty fields. It never creates rooms or blocks, and
never changes IDs, codes, blocks, floors, aliases, room sources or entrance choices.
Missing records are reported; `seed_campus` can create the prepared inventory if
it is absent. Never run these commands against production or an unrelated database.

The updater is atomic and locks each target row. A room text field is changed only
when empty or exactly equal to its allowlisted legacy seed value. Approved values
are unchanged. Different manual text is retained and reported to stderr, for example:

```text
Conflict: D117.description differs from the old seed and approved text. Existing value preserved.
```

Faculty name/source are treated as a pair: an existing manual name or provenance
is retained and reported rather than relabelled as team information. Unknown H/I
faculties are not filled. Review reported conflicts and make an explicit correction
through the models/admin workflow; the updater has no force-overwrite option.
A preserved manual room field does not stop other safe, independent fields being
updated. Successful runs report updated room/block counts and conflict count.

Fresh installations use `migrate` followed by `seed_campus`: new barrel names and
descriptions are English, and known faculties are populated. Seed calls the same
updater for existing rows, so its repeat behavior also preserves manual edits.
Approved descriptions and faculty values exist in one backend module,
`campus/approved_details.py`, shared by both commands. The legacy texts there are
only an explicit update allowlist, not a separate room inventory.

## Content and provenance

Barrels A→B→C→D are described in order from the main entrance. Their first/second
floor labels and room aliases remain unchanged. Barrel D2 is E221 in block E;
Barrel A1 is D117 in block D. No turns, distances or corridor routes are inferred.

| Block | Faculty from the team-provided diagram |
| --- | --- |
| D | Faculty of Law & Social Sciences |
| E | Faculty of Education & Humanities |
| F | Faculty of Engineering and Natural Sciences |
| G | SDU Business School |
| H, I | Not confirmed |

`faculty_source` is `Team-provided campus diagram; not independently verified`.
The information is not presented as an independently verified current university
structure. Red Canteen in the descriptions is not equated with the entire approved
Canteen shape. It has no separately confirmed marker on this schematic.

## API and presentation

Search and location results contain the full `description` and a nested `block`
with id, code, name, faculty_name and faculty_source. Faculty searches match the
block's stored faculty_name, including partial and case-insensitive queries; they
return the corresponding block. Existing room code/name/alias searches are retained.
Related block fields are included via the existing select_related joins without
new N+1 queries.

`GET /api/campus/blocks/` returns the actual six inventory blocks' same metadata
for SVG captions. It uses the existing session and CSRF conventions, returns 401
without a session and retryable 503 on database failure, and is not cached. It does
not create context blocks A–C or duplicate any inventory in the frontend.

The SVG wraps faculty captions into the existing left label column. Geometry,
entrance markers, corridors, Canteen, barrels and context blocks are unchanged.
On screens up to 650 px the faculty captions are hidden to keep short block labels;
the complete faculty name stays visible in the selection card. Descriptions are
full, wrapping text, never tooltip-only. Unknown H/I faculties are explicit.

## Verified locally on 2026-10-07

- The schema migration applied successfully to project PostgreSQL.
- First update: 8 rooms and 4 blocks updated, zero conflicts. Second update:
  zero rows updated, zero conflicts; no duplicates or structural changes.
- Django check and migration consistency passed; all 161 accounts/core/campus
  tests passed, including fresh seed, legacy/empty upgrades, idempotence,
  manual conflict preservation, missing rows, all eight number/alias/name searches,
  identical search/map descriptions, faculty search, catalog authorization and
  one-query metadata loading.
- Frontend production build passed.
- All eight barrels were checked in the browser from alias search to Show on map;
  complete description text matched in both cards.
- Direct D2 selection and refresh restored its full English description/faculty,
  with E, physical barrel D and MAIN highlighted.
- Faculty of Education & Humanities search returned Block E and its full map card.
- Mobile 390×844 showed the long D2 description as normal wrapping text, with page
  width equal to the viewport and no horizontal overflow.

All requested checks were completed. A temporary browser approval timeout was
resolved on retry; no security bypass or production access was used.
