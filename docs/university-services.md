# University service information (Story 8)

User story: As a user, I want to view a university service location, opening hours,
and published contacts so that I can plan my visit.

## Data and unknowns

The existing CampusPlace model stores services; is_service distinguishes them
from Library and auditoriums. Room, Block and map bindings are reused.
CampusPlace adds separate working_days, lunch_break, document_collection_hours,
weekly_hours, schedule_note, schedule_sources, contacts, service_staff and
extra_photos fields. No duplicate database or service room model is introduced.

| Service | Location | Known schedule |
| --- | --- | --- |
| Student Service Center | D109, Block D, floor 1 | Monday–Friday 09:00–18:00; lunch 12:30–13:30 |
| Advising Desk | Opposite SSC D109; own room, block and floor left unset | Monday–Friday 09:00–18:00; document collection 13:00–15:00; lunch 12:30–13:30 |
| International Relations Department | E109, Block E, floor 1 | Monday–Friday 09:00–18:00 |
| Medical Center — CK-MED | G109, Block G, floor 1 | Monday–Friday 09:00–18:00; Saturday 09:00–13:00; Sunday closed |

Advising Desk explicitly explains the overlap between document collection and
lunch: availability from 13:00 to 13:30 requires clarification. Both published
values are preserved; document collection is never treated as full opening hours.
Both SSC and Advising Desk refer Moodle questions to F105. F105 is not the SSC
or Advising Desk location. The owner subsequently supplied Monday–Friday,
09:00–18:00 for all services; migration 0009 applies this explicit correction.
These weekday hours are attributed to the owner, not inferred from photographs.

The owner provided published email contacts: SSC and Advising Desk use
ssc@sdu.edu.kz, International Relations uses iro@sdu.edu.kz, and CK-MED uses
medpunkt@sdu.edu.kz. Migration 0010 appends them while retaining other contacts;
new seeds include them. Other unpublished contact details remain unknown.
Named staff from signs are separate service_staff entries, not invented email or
phone contacts or automatically assigned Teacher accounts. The three Advising
Desk staff names/roles and Abbas Bodaubekov's directorship are retained as supplied.

No Open now status is calculated because the schedules are incomplete or
conflicting. No timezone-dependent status exists in this implementation; any
future status calculation must use Asia/Almaty and account for missing days,
breaks and the Advising Desk conflict.

## Permanent photographs

The original IMG filenames were not on disk. The owner subsequently attached
five matching clipboard PNGs. Their content was matched to the supplied roles
and copied unchanged into frontend/public/campus/places/:

| Original description | Permanent asset |
| --- | --- |
| IMG_5522: SSC general view | student-service-center.png (cover) |
| IMG_5521: D109 door and notice | student-service-center-notice.png (additional) |
| IMG_5523: Advising Desk sign | advising-desk.png |
| IMG_5524: E109 sign | international-relations.png |
| IMG_5525: G109 CK-MED entrance | medical-center.png |

URLs start /campus/places/ and contain no temporary local paths.
PhotoGallery provides English alt text, lazy thumbnails, preserved image
proportions, unavailable-image feedback, and an enlarged native dialog closed
with Escape or Close photo. Cover and additional images remain separate;
SSC's door notice never replaces its general-view cover.

## Installation and updates

Use the project's local PostgreSQL configuration. From the repository root:

```sh
.venv/bin/python backend/manage.py migrate
# Only on a fresh installation without campus blocks:
.venv/bin/python backend/manage.py seed_campus
.venv/bin/python backend/manage.py seed_campus_services --dry-run
.venv/bin/python backend/manage.py seed_campus_services
.venv/bin/python backend/manage.py seed_campus_services
```

Seed uses stable place slugs and normalized existing room codes/aliases. New
D109/E109/G109 inventory is created only when absent. Existing room fields,
contacts, opening hours, staff and other place data are never overwritten.
Existing differing fields are reported for manual review. Other E109 landmarks
keep their room and map bindings. Dry-run rolls back database changes; sequences
may advance. Repeated seed must create zero places and zero rooms.

Manage service data in Django Admin -> Campus places, filtering is_service.
These entries remain UNVERIFIED as whole records: source attribution and partial
schedule confirmation are not presented as verification of every missing field.

## API and UI

- GET /api/campus/services/ returns up to 100 service records.
- GET /api/campus/services/?slug=student-service-center returns one record;
  unknown slug is 404, oversized slug is 400, database failure is 503.
- Existing session protection returns 401 without a valid session. CSRF and
  account behavior remain unchanged.
- GET /api/campus/search/?q=D-109 finds the existing room and linked service.
  Services are searchable by name, aliases and linked room code.
- Existing GET /api/campus/location/?type=place&id=... returns the same service
  details and its explicit map binding.

Open #services through Home or the shared Services navigation link. The search
field filters the loaded list by name, aliases and linked room code, ignoring
case, spacing and code hyphens. Its query is retained in the URL across refresh,
details and return to the list; Clear search restores all services. Select a
service to open #services?slug=...; refresh restores the detail. List, Search and
Map use the same backend data and FacilityCard/ServiceDetails/PhotoGallery.
Missing fields render Not provided; loading, errors/retry and session expiry
are handled. No contacts are synthesized from staff names.

SSC, International Relations and CK-MED have building-level block bindings and
Show on map. Advising Desk has only its textual landmark and no active exact-point
map action. No new coordinates, room contours or map geometry are invented.

## Verification

```sh
.venv/bin/python backend/manage.py check
.venv/bin/python backend/manage.py makemigrations --check --dry-run
.venv/bin/python backend/manage.py test accounts core campus --keepdb
npm --prefix frontend run build
```

On 2026-10-15, 197 backend tests passed, including 11 service tests for schedules,
unknown values, staff versus contacts, photos, search/map, validation, dry-run,
repeat seed and preservation of contacts/room data/E109 landmarks.
Local migration and seed created four services and three rooms; repeat created
zero. Frontend build and migration consistency checks passed.

Chromium checks passed for Home -> Services, all four details and photo bindings,
full-image dialogs/Escape, SSC cover/additional ordering, separate hours/lunch/
document collection, unknown values and staff/contact separation, map selection
and refresh, normalized room search, map search, 390px layout, 503/retry and
401/session expiry. No JavaScript page errors occurred. The temporary local
QA account was removed after verification.

## Implementation files

- backend/campus/models.py and migrations/0008_campusplace_contacts_and_more.py
- backend/campus/management/commands/seed_campus_services.py
- backend/campus/service_views.py, places.py, views.py and admin.py
- backend/config/urls.py and backend/campus/test_services.py
- frontend/src/ServicesPanel.jsx, AuthPanel.jsx and HomePanel.jsx
- frontend/src/campus/FacilityCard.jsx, PhotoGallery.jsx and ServiceDetails.jsx
- frontend/src/campus/facility-card.css
- The five permanent PNG assets listed above
- README.md and docs/university-services.md

Remaining data questions: Advising Desk's own room and overlap availability;
weekend availability for SSC, Advising Desk and International Relations;
published contacts for all four services. CK-MED's published weekend hours remain.
