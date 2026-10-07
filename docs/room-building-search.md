# Story 6 — Room and Building Search

Only inventory search is implemented here. Map, routing, geolocation, chatbot,
services and faculty directory remain outside this story.

## Local setup

Start the project-owned PostgreSQL cluster and use the existing `.env` and venv.
Never run these commands against production or an unrelated database.

```sh
source .venv/bin/activate
python backend/manage.py migrate
python backend/manage.py seed_campus
python backend/manage.py check
python backend/manage.py makemigrations --check --dry-run
python backend/manage.py test accounts core campus --keepdb
npm --prefix frontend ci
npm --prefix frontend run build
python backend/manage.py runserver 127.0.0.1:8000
# In another terminal:
npm --prefix frontend run dev
```

Open http://127.0.0.1:5173, sign in, enter E204 on Home and press Enter or Search.
The URL becomes `#search?q=E204&page=1`. Refresh retains the query and results.
Search also accepts `e204`, `E2`, `E`, `Блок E`, `Бочка A1`, `A1` and room names.
No record is inferred or created from a number. `I02` is valid basement numbering
but will return no result unless that room has been entered into the inventory.

## Prepared data

The campus app, initial migration, numbering helper and atomic seed command were
imported from `sdu-campus-database-2.zip` using `campus-data.patch`. Only the
`campus` setting was added to the existing configuration; the archive's README
was not substituted for the project's README. See [campus-data.md](campus-data.md).

There are six blocks D–I, three entrances and 128 seeded rooms (120 generated,
eight team-reported barrels). Re-running seed preserves corrections. Room entrance
overrides take precedence over their block. Because the supplied Room schema has
no separate override confidence, an override is returned with UNKNOWN confidence;
the API never borrows the block's status for a different recommendation.
Generated rooms retain a provisional flag based on their source; blank sources
are also treated as provisional. Fourth-floor UNKNOWN rooms are not called staff
offices. Barrel D2 is room E221 in block E.

## API

`GET /api/campus/search/?q=E204&page=1&page_size=20`

Uses the existing session cookie and CSRFAuthentication convention. Anonymous or
expired sessions return 401; database outages return retryable 503. GET has no
side effects. Existing CSRF and account endpoints are unchanged. Responses are
not cached. No authentication tokens are stored in localStorage.

Query length is limited to 80 raw characters, pages to 1–100 and page sizes to
1–50 (default 20). Invalid bounds return 400. An empty query returns an empty
list rather than the whole inventory. The client uses the server's next_page.
Count is the complete matched count; traversal is limited to the first 100 pages.
Each source fetches at most page × page_size rows (at most 5,000) for a bounded
merge; no unbounded Python inventory scan is used.

Case and repeated whitespace are normalized. Room codes also use the prepared
normalize_room_code, including Cyrillic Е/І. Russian case matching is independent
of the PostgreSQL cluster locale. Aliases are matched as individual JSON array
strings; SQL parameters and literal LIKE escaping keep user input out of SQL.
Explicit block queries return that block and its rooms, avoiding incidental
matches against aliases in other blocks. Exact code/alias matches precede partial
matches, with stable code/type ordering. Names are also searched. Related block
and entrance records use select_related; search uses four inventory queries
(two counts and two bounded fetches), independent of result count.

Response fields:

- query, count, page, page_size, next_page, results.
- Each result: id, type (`room` or `block`), code, name, block (id/code/name),
  description, entrance, source, provisional.
- Rooms additionally include floor (0 = basement) and kind. Blocks have no floor.
- entrance: code/name/description, status (`USER_REPORTED`, `PROVISIONAL`,
  `UNKNOWN`) and note. A missing entrance has null code/name.

## Interface and verification

Search replaces the previous Search placeholder. It has an accessible labelled
form, Enter submission, focusable links, a results heading, loading/live status,
empty guidance, no-results message, retryable error and numbered pagination.
Changing a query or leaving the page aborts its request; stale results cannot
replace a later search. API requests also have a 15-second deadline.
Hash route parsing separates the route name from query parameters for session
protection. Expiration returns to login. No map button, distances or shortest-path
claims are shown. Existing account/profile/home screens are retained.

Backend coverage includes case/spacing, aliases, barrel D2, partial/name/block
search, H→G, confidence and sources, UNKNOWN fourth floors, room overrides,
unknown inventory, anonymous access, query/page bounds, stable pagination,
literal wildcards, database failures and query counts. Prepared seed and numbering
tests also run alongside all existing account/core tests.

### Verified locally on 2026-10-07

- Django check: no issues; migration consistency: no changes detected.
- The prepared migration applied to project PostgreSQL; seed created 128 rooms,
  then created zero on a repeat run. Existing seed tests verify manual edits.
- `test accounts core campus --keepdb`: 143 tests passed (including 123 existing
  account/core tests). Python dependency consistency also passed during setup.
- `npm --prefix frontend run build`: passed using the committed npm lockfile.
- Browser: Home → E204 via Enter, preserved URL/results after refresh, barrel D2
  → E221/block E/floor 2, 20+3 results across pages for E, unknown-room empty
  results, empty-query guidance, API error/retry, isolated test-session expiration,
  protected URL with parameters, and quick successive searches ending at A1.
- Mobile 390 × 844: input/button/cards readable; document width equals viewport,
  no horizontal overflow. Temporary viewport override was reset afterward.

A real network outage was not injected in the browser. Its error panel was checked
using an API validation error; database failure handling is covered by backend
fault-injection tests. No production database was accessed.

### Card presentation update

Cards omit team attribution, recommendation notes, generated-inventory boilerplate,
provisional-inventory badges and source lines. Meaningful room descriptions (such
as barrel locations) remain visible, as do provisional/unknown entrance confidence
labels. All provenance and inventory flags remain available in the API/database.
