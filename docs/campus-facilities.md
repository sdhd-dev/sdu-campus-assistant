# Library and auditoriums

Use existing CampusPlace; no fake numbered Room or new Block records are created.
Upgrade the local project database:

```sh
python backend/manage.py migrate
python backend/manage.py seed_campus_places
```

The command creates Library, Red Hall and Mini Red Hall using stable slugs. Repeat
creates no duplicates; any differing existing fields are reported and preserved.
Review/edit through Django admin when appropriate. Unknown floors, room IDs,
opening hours and entrance markers stay blank. Verification applies to the
team-confirmed descriptions/relative locations, not unknown exact coordinates.

Library: existing `library-area` schematic binding; three floors and separate
outdoor entrance. Floor numbers, exact area boundaries and outdoor entrance
position remain unknown. Red Hall: category AUDITORIUM, `block:A` binding and
location text Block A; the Block model remains D–I, so no invented Block A database
record is added. Mini Red Hall: AUDITORIUM, `near-entrance:G`, approximate region
around the existing Entrance G marker; no block or floor is inferred.

Both English and Russian aliases participate in the existing normalized search.
Exact Red Hall ranks above Mini Red Hall for "red hall", which returns both.
The session-protected catalog returns actual facility IDs for SVG labels and
buttons; no frontend inventory or hardcoded facility IDs exist. Location returns
one explicit map binding, without inventing recommended entrances.

CampusPlace now adds location, details (short strings), photo, photo_alt and
map_note. Existing JSON import accepts these optional fields plus AUDITORIUM.
Photos must be project paths `/campus/places/<name>.webp|jpg|png` with alt text;
path traversal and external photo URLs are rejected. Shared FacilityCard renders
the same backend metadata in search and map, with lazy thumbnails, full photo
modal (Escape/Close), and an unavailable-photo fallback. On mobile the selected
facility map precedes the card; previews are 80px high and longer location notes
can be expanded.

User-supplied processed photographs (already without white panorama arrows) are
saved as library.webp, red-hall.webp and mini-red-hall.webp. They are resized to at
most 1400px wide and WebP quality 82 (approximately 156–204 KiB); no fabricated
image content is introduced.

Team follow-up: library floor numbers, exact boundaries/outdoor entrance position;
Red Hall's floor and exact auditorium position; Mini Red Hall's exact position,
block and floor; opening hours if relevant. Existing Accounting Office and Red
Canteen location questions remain unresolved. The overall SVG path geometry and
removed side block are unchanged.
