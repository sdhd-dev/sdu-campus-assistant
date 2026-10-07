# Campus demo polish

## Ready, planned, and provisional

Ready: session authentication/profile, unified room/block/barrel/facility search,
2D schematic selections, full descriptions/faculty metadata, keyboard barrel
floor choices, URL restoration, responsive Home and shared navigation.
Services and Directory are planned; their direct links explain this.
No floor plans, routing, geolocation, 3D or staff directory are provided.
Generated rooms still require an existence survey. G/I entrance recommendations
and Entrance I position remain provisional. H uses Entrance G, between G and H.
Library area is only a schematic annotation. Red Canteen is not synonymous with
the entire Canteen shape. No records for future facilities are seeded.

## Update a local database

Start your project PostgreSQL (see README), activate `.venv`, then:

```sh
python backend/manage.py migrate
python backend/manage.py update_campus_details
# New inventory only, if not already seeded:
python backend/manage.py seed_campus
python backend/manage.py runserver 127.0.0.1:8000
npm --prefix frontend run dev
```

The updater translates allowlisted old/empty barrel and entrance text and
recommendations; it retains manually changed text and prints conflicts. It never
changes room codes, floors, IDs, entrance links or confidence. Review conflicts
before updating through admin. Commands affect the database configured for the
process; use the local development configuration, never production for demos.

## Facilities through Django admin

Create an administrator explicitly with `python backend/manage.py createsuperuser`.
Open http://127.0.0.1:8000/admin/ directly (Vite only proxies `/api/`).
Django `is_staff` plus model permissions control access; profile affiliation Staff
never grants admin rights. A superuser can add/edit Campus places, Room, Block and
Entrance. The stable place slug is read-only after creation in admin.

CampusPlace is separate from numbered Room. It stores a stable slug, name,
category (LIBRARY/OFFICE/HALL/FOOD/OTHER), aliases, English description, optional
block/floor/Room/entrance, existing map binding, plain-text opening hours, source,
verification status and verification date. Unknown fields stay blank/null; 0 means
basement. A linked Room supplies missing block/floor; explicit values must agree.
A verified place needs source and date. Aliases are a JSON string array.

## JSON import

One format, maximum 1 MB / 500 places. UTF-8 example below is **synthetic**, not
campus evidence; replace it with surveyed data before importing:

```json
{
  "version": 1,
  "places": [{
    "slug": "survey-example",
    "name": "Survey example (replace before use)",
    "category": "OTHER",
    "aliases": ["Example alias"],
    "description": "Replace with a checked English description.",
    "block": null,
    "floor": null,
    "room": null,
    "recommended_entrance": null,
    "map_element": "",
    "opening_hours": "",
    "source": "Replace with survey evidence",
    "verification_status": "VERIFIED",
    "verified_at": "2026-10-07"
  }]
}
```

```sh
python backend/manage.py import_campus_places verified-places.json --dry-run
python backend/manage.py import_campus_places verified-places.json
```

Only verified rows are accepted. Relationships use existing codes (e.g. E,
E204, MAIN), never database IDs. Unknown keys, invalid categories/floors/aliases,
missing references, duplicate slugs and incomplete verification fail the whole
transaction. Repeating identical data makes no changes. Differing supplied fields
cause a conflict and rollback; omitted optional fields stay unchanged. After
review, `--update --dry-run`, then `--update` explicitly replaces supplied fields.
Dry-run validates the same path and rolls back every write. Never use `--update`
without reviewing manual corrections.

## Binding to the schematic

`map_element` is blank or one of `block:A` through `block:I`, `barrel:A` through
`barrel:D`, `entrance:MAIN`, `entrance:G`, `entrance:I`, `canteen`.
Select an existing shape only when its association is checked. Metadata alone
never creates a binding or a highlight. No coordinates are stored or invented.
Block bindings must agree with explicit block metadata. A facility without a
binding is searchable, shows unknown fields, and has no Show on map link; even a
direct location API request does not highlight a random block.

## API additions

All campus endpoints require the existing session, return 401 for anonymous or
expired sessions, and preserve CSRF protections.

- `GET /api/campus/catalog/`: actual barrel Room IDs/labels plus quick places A1
  and existing blocks D–G. Missing records are omitted. Database failure is 503.
- Search now merges CampusPlace with Room/Block using the same query limits,
  stable exact-first ranking and pagination. Related metadata uses select_related.
- `GET /api/campus/location/?type=place&id=ID`: facility metadata and explicit
  map element. Invalid ID 400, missing row 404, database failure 503.
- Room/block entrance metadata includes the English description. Entrance G:
  “Located between Blocks G and H.”

## Team data collection

For Library, Accounting Office, Red Hall, Advisor Desk and Red Canteen, record
name/aliases/category, checked English description, block/floor/room if known,
entrance (with evidence), hours (date checked), source and verification date.
Confirm the relationship to an existing schematic element separately; leave it
blank until confirmed. Collect faculty details for H/I, actual room existence,
Entrance I position and the G/I recommendations. Do not infer floors or schedules
from the Library annotation or distances from this schematic.

## 2–3 minute demonstration

1. Home: explain search as the primary action; enter E204 and press Enter. Show
   Block E, Floor 2 and Main entrance. Explain generated room existence needs
   checking. Show on map and point out the faculty and entrance.
2. Home: search Barrel C1. Read the full first-floor description near Advisor Desk;
   open the map. Click/press Enter on Barrel C and select C2 / Floor 2.
3. Choose Barrel D then D2. Show E221 in Block E, physical Barrel D and MAIN.
   Refresh to demonstrate preserved selection. Select Entrance G and show its
   location between G/H. Close by identifying planned features and survey gaps.

## Validation

Django check, migration drift check, 170 accounts/core/campus tests and Vite build
passed. Tests cover import dry-run/atomic invalid input/repeat/conflict, admin
permission separation, unmapped facilities, actual barrel catalog, descriptions,
expired sessions and existing search/map behavior. Browser verification results
are reported with the implementation; this document does not claim production
readiness.
