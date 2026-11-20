# Staff directory and listed offices

## Scope and source quality

The directory extends the existing session-protected campus search and 2D map.
There is no 3D or chatbot implementation to extend; no new AI service is added.
All UI labels and explanatory messages are English. Display names use Latin
letters; existing Latin spellings remain unchanged. Cyrillic/Kazakh names use
deterministic transliteration with their order and initials preserved. This is a
display convention, not verified official Latin spelling. Dr is a separate title;
the original line remains in source_name. At the owner's explicit request,
undefined roles are assigned TEACHER; existing defined roles are preserved.
This classification comes from the owner's instruction, not photo evidence.

The supplied teachers_campus_assistant.md transcribes three photographs.
The photographs themselves were not attached, so no spelling or allocation was
independently checked. All 205 named entries are included as LISTED at the owner's
request, including 52 with unresolved notes in teachers-review.json. LISTED does
not mean verified spelling or current occupancy. Source data and review reasons
remain stored. At the owner's request, cards omit the office-list, provisional-room,
provisional-entrance and room-position qualification captions.
The last two G-407 names retain spelling and office-association review notes.
The obscured D-213/1 line has no recoverable name and is not a person record.
PED, WE and room-purpose labels are never imported as people; office hours
on the source sheet is a room purpose, not an opening schedule.

Versioned files in backend/campus/data/:

- teachers-source.md: unchanged supplied source, including its embedded prompt
  (the importer does not execute that prompt).
- teachers.json: curated importable records with stable source keys.
- teachers-review.json: included names with unresolved source review notes.
- build_teacher_dataset.py: reproducible extraction with per-name review reasons.

The source identifies image(4).png, image(5).png, image(6).png collectively.
Per-record image attribution is unknown; source_image remains empty rather than
inventing a mapping. Obtain originals to resolve the 52 review entries and record
the actual image and verification evidence before releasing corrections.

## Models and mapping

DirectoryFaculty and Person are in the existing campus app. OfficeAssignment
provides the many-to-many person/room association, faculty, source room label,
door and alternate label. A name is not a globally unique person identifier.
Search does not merge homonyms. Stable import keys identify source entries;
manual people use a separate unique source_key. Review people are excluded from
search and room/map cards even if an administrator creates them.

Faculty mapping is explicit: SSBL -> D/G, SITAM -> F/I. The owner clarified SITAM
as School of IT and Applied Mathematics on 2026-10-15. Migration 0007 updates
both F/I block labels and the directory faculty name to this designation.

Room uses the existing schema (G206, F213, I204). The source label G-206 or
F-213/2 remains on the office association. Door suffixes /1, /2, /3 mean
right, central, left. Hall labels remain HALL. D-212 keeps alternate label
213/3 without creating another person or assuming D213 is the same office.
G-214 is on floor 2. Existing rooms/aliases are reused; new source-listed offices
use STAFF_OFFICE with provisional source provenance. Existing kinds, descriptions,
entrances and manually corrected records are preserved.

Missing room links are allowed. Linked rooms open the existing building-level
map selection; unlinked offices show Map location not recorded, with no active
map action. No exact room positions, routes, contact details or schedules are inferred.

## Local installation

Use only the project's local PostgreSQL environment; never target production.
Activate the existing virtual environment and run from the repository root:

```sh
python backend/manage.py migrate
# For a new, empty campus installation only:
python backend/manage.py seed_campus
python backend/manage.py import_teachers --dry-run
python backend/manage.py import_teachers
python backend/manage.py import_teachers
```

The import is transactional. Dry-run performs the same work and rolls back
records; PostgreSQL sequence numbers can advance. Repeated imports use stable
source keys and preserve every existing person's and assignment's fields, not
just names. They neither delete records nor overwrite manual corrections.
Ambiguous room aliases abort the transaction for review.
The second run should report zero new people, offices and rooms.

For a changed transcription, review dataset diffs and stable keys before import:
do not reorder people or reuse old keys for a different person. Existing
records are deliberately not upgraded automatically; reconcile changes in admin.
The importer prints creation and preservation counts.

## Search and API

GET /api/campus/search/?q=Aleksei&page=1 optionally accepts faculty=SSBL or SITAM.
Staff Directory also passes type=person so its results contain people only;
Home and Map keep the combined search.
The existing 80-character query, 1-100 page, 1-50 page_size limits and session
authentication remain. A faculty filter limits results to people in that faculty;
without it all existing search types remain enabled.

Person search uses Unicode NFKC/casefold and collapsed whitespace, with exact
display/source-name matches ranked before partial names. Original Cyrillic names
remain searchable. A derived Latin search key accepts common cross-script
variants (Aleksei/Aleksey, Q/K, Kh/H). These keys retrieve candidates only;
they never merge or identify two people.
Results have type=person, id, name, title, source_name, role, source,
source_image, verification_status, offices and map_available. Each office has
source_room, door, faculty, alternative_label, room (id/code/block/floor or null),
map_available and the occupancy qualification. Multiple offices produce separate
map actions in one person card. Deleted room links do not delete the person.

Room search and GET /api/campus/location/?type=room&id=... include people listed
for that office. Search batches office/person/faculty loading using prefetch;
catalog uses the same prefetch and serialization. Person result pagination is
merged deterministically with existing room, block and facility results.

Open #directory from Home, or type a name into Search or Campus Map.
In Search, select a faculty and press Search. The query, page and applied
faculty filter persist in the hash. Person cards use a shared component in Search
and Map search; Show on map opens the existing room identifier. The room card
shows the same listed people, including their separate door labels.

## Verification

```sh
python backend/manage.py check
python backend/manage.py makemigrations --check --dry-run
python backend/manage.py test accounts core campus --keepdb
npm --prefix frontend run build
```

Directory tests cover curated/review separation, names and Dr, Unicode/case,
partial names, shared rooms, homonyms, multiple offices, no map link, faculty
filters, pagination, sessions, G-214 floor, door labels, idempotence, dry-run,
manual preservation and constant serialization query counts.

Local verification on 2026-10-15: the initial import added 153 people and 53 rooms.
The owner-requested complete list then added 52 people/office assignments and
5 rooms, reaching 205 people and 205 office assignments. Existing names were
transliterated with original source names retained, and undefined roles became
TEACHER. A repeated complete import created zero records and preserved 205 people.
All 186 accounts/core/campus tests, Django system checks, migration consistency
checks and the frontend production build passed on the completed implementation.
Chromium checked person search -> office/map -> refresh, search on the map,
directory entry, F-213/3 left-door label, faculty filtering and URL restoration,
390px search and map overflow, existing E204/Barrel D2/Library search, and no
JavaScript page errors. A temporary local QA account was used and removed.

Remaining verification work: original photographs, the 52 included flagged entries, exact
image attribution, current office allocation, D-212/213/3 relationship, SITAM's
official expanded name, and any unpublished contact or reception information.
