# Story 7 — View Location on a 2D Map

The map uses the approved `sdu-campus-map.html` SVG in React, not an iframe.
No preview wrapper, script, external CDN dependency or demonstration room array
is included. Paths, circles, labels and corridor connections are preserved.
The map is schematic, not to scale, and does not show room positions or routes.

## Start and use

Use the existing PostgreSQL cluster, `.env` and virtual environment from README.
There is no new database or schema migration for Story 7.

```sh
source .venv/bin/activate
python backend/manage.py check
python backend/manage.py migrate
python backend/manage.py seed_campus
python backend/manage.py makemigrations --check --dry-run
python backend/manage.py test accounts core campus --keepdb
npm --prefix frontend ci
npm --prefix frontend run build
python backend/manage.py runserver 127.0.0.1:8000
# Another terminal:
npm --prefix frontend run dev
```

Sign in at http://127.0.0.1:5173, search for E204 on Home, and choose **Show on map**.
The selection card reads `E204 · Block E · Floor 2 · Main entrance`, with block E
and MAIN highlighted. Campus Map on Home opens an unselected overview.
The map's search uses the Story 6 API. One unambiguous result opens automatically;
partial searches offer result links and a link to the full paginated search.
Controls and captions are English. Stored inventory descriptions remain source data.

Click a block or entrance on the SVG, or use the labelled buttons below the map.
SVG targets respond to Enter and Space. Selected objects have yellow fill, a dark
outline and a text selection card, plus pressed button states. Tab focus has a
separate outline. Zoom ranges from 100% to 300%; zoomed maps scroll horizontally
and vertically. Reset restores the fitted overview and scroll origin, keeping
selection. On mobile the selection card precedes the drawing. No exact room
coordinates, distances, shortest-route claims or geolocation are provided.

## URL and API

Hash routes accept both the existing `#map` and slash form `#/map`:

- `#/map?type=room&id=29` — room database ID (example local ID; IDs vary by database).
- `#/map?type=block&code=E` — block code.
- `#/map?type=entrance&code=MAIN` — entrance code.

Refresh and direct links resolve their selection through
`GET /api/campus/location/?type=...&id=...` or `&code=...`.
IDs must be positive integers of at most ten digits; codes have at most four
characters. Invalid selectors return 400; missing inventory returns 404; database
outages return retryable 503. Responses are not cached. Anonymous or expired
sessions return 401 and the frontend returns to login, including slash routes
with query parameters. Existing session and CSRF behavior is preserved.

Room/block responses retain the Story 6 fields, plus:

```json
{
  "map": {
    "block_code": "E",
    "entrance_code": "MAIN",
    "barrel_code": "D",
    "barrel_label": "D2",
    "context_only": false,
    "entrance_position_provisional": false
  }
}
```

The barrel fields are null for an ordinary room. Standalone entrance selections
have no block highlight. Related block/entrance data are fetched in one query for
a room selection. No GET creates inventory. Missing entrance information, unknown
selectors, missing SVG figures, loading and API failures have explicit UI states.
Retry location and Retry search reissue their requests. Changing selection aborts
its earlier request; choosing a block cancels an outstanding search so it cannot
later replace the chosen location. Requests have the existing 15-second deadline.

## Model-to-SVG binding

- `Block.code` matches the SVG group's `data-block` (A–I).
- `Room.block.code` chooses the building shape; there is no coordinate per room.
- `Room.effective_entrance.code` matches `data-entry` (MAIN/G/I), including a
  room-specific override. The prepared Room schema has no override confidence,
  so it remains UNKNOWN rather than inheriting a different recommendation.
- For kind BARREL, backend aliases/name identify A1/A2 through D1/D2. Their letter
  selects the physical `data-barrel` circle; the full label is returned separately.
  Ambiguous or unsupported aliases have no guessed physical barrel highlight.
- E221 / Barrel D2 highlights block E and barrel D, not block D.

The geometry lives in `frontend/src/map/CampusMap.jsx`; styling in `map/map.css`;
URL selection and controls in `MapPanel.jsx`; selection resolution in
`backend/campus/map_views.py`. The finite SVG code lists describe geometry, not
room inventory. All room existence and entrance choices come from PostgreSQL.

A–C are context shapes near the main entrance. Their selection response is a
minimal, explicitly unconfirmed context object, without inserting Block or Room
records and without assuming an entrance or service. B retains the approved
Library area annotation with a boundary warning. The deleted side C near G is
not reintroduced: the SVG contains exactly one C near the main entrance.

## Adding or correcting places

Correct rooms/entrances through the existing campus models; seed preserves manual
changes. An ordinary room only needs its real block/floor and optional entrance
override. For a barrel, retain a consistent verified alias such as D2; do not
infer physical barrel identity from its block letter. To add new building or
entrance geometry, obtain an approved diagram, update the SVG group/marker and
its finite geometry list, and add corresponding campus inventory after validating
it. An inventory object without geometry reports that the map shape is unavailable.
Do not add arbitrary coordinates, office services or room positions.

## Unconfirmed data

- The Library area boundary needs confirmation.
- Entrance I position is provisional; its marker and card retain that warning.
- G/I recommendations can be provisional; H uses the team's G recommendation.
- Generated rooms retain their provisional existence warning in map cards.
- Accounting Office and Red Hall have no confirmed position and no invented pins.
- A–C facility details and entrance recommendations are not confirmed.
- Fourth-floor UNKNOWN rooms remain unclassified; no teacher office inference.

## Local verification (2026-10-07)

Django check and migration consistency passed; all 153 accounts/core/campus tests
passed. Coverage includes E204/H, every barrel alias, overrides and missing entrances,
context objects without database writes, unknown IDs, anonymous access, cache
headers, bounded selectors, database failure and a one-query room lookup. The
frontend production build passed. A geometry comparison confirmed every SVG path,
circle coordinate/radius and text position matches the supplied prototype.

Browser checks covered Story 6 → Show on map → E204, refresh persistence, H204→H/G,
Barrel D2→E/barrel D/MAIN, a temporary local test room using MAIN instead of its
block's I entrance, unknown room ID, keyboard activation of an SVG block, context
A, zoom in/out/reset and mobile 390×844 with no page overflow. A brief shutdown of
the local development backend produced the error panel; restarting and choosing
Retry location recovered the same selected block. Temporary test data were removed.
No production database or existing pull request was merged during implementation.

Expired-session handling and anonymous direct `#/map` links with parameters were
also checked in the browser and returned to sign-in.

### Description and faculty follow-up

Map selections now render full room descriptions and faculty metadata. Faculty
labels come from the session-protected `/api/campus/blocks/` endpoint, with short
block labels retained on mobile. Block has two additional schema fields for this
follow-up; use [campus-details.md](campus-details.md) for the required migration
and conservative update command for existing databases.
