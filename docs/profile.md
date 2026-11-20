# US-04: profile type selection

> Since [US-07](verified-roles.md), Student and Staff require email verification;
> only Visitor can be chosen freely. The API and checklist below note the changes.

Signing in now opens a profile view instead of the previous signed-in panel. It
shows the account email and offers **Student**, **Staff**, and **Visitor** as
three native radio cards with a short description of each affiliation. The saved
value is restored on load, after a refresh, and at the next sign-in. `profile_type`
already existed on the user model from US-01, so no migration was added. No
dependencies were added.

## API

`profile_type` is the only writable field. The account is always taken from the
session; the request body cannot name another user.

| Endpoint | Behavior |
| --- | --- |
| `GET /api/profile/` | 200 with `email`, `profile_type`, `profile_types`, and `csrf_token` for an active authenticated user; otherwise 401 with `{"detail":"Authentication required."}`. |
| `PATCH /api/profile/` | Requires the CSRF cookie and `X-CSRFToken`. Accepts exactly `{"profile_type": "STUDENT"}`, `"STAFF"`, or `"VISITOR"` and returns the same body as GET. Since US-07, STUDENT/STAFF must match the verified status (400 otherwise). |

`profile_types` is the server's list of `{value, label}` options; the page renders
those and never invents a value. Responses disable caching and contain no password,
hash, or privilege field. `POST`, `PUT`, and `DELETE` return 405.

Rejections:

- Any unsupported value returns 400 with `{"profile_type":["Choose Student, Staff, or Visitor."]}`.
  The submitted value is not echoed back.
- Any other field — including `is_staff`, `is_superuser`, `is_active`, `groups`,
  `user_permissions`, `email`, `password`, and `id` — returns 400 with
  `{"non_field_errors":["Only profile_type is accepted."]}`, whether sent alone or
  alongside a valid `profile_type`. Nothing is written.
- A missing or invalid CSRF token, or an untrusted `Origin`, returns 403 and leaves
  the stored value unchanged.
- An expired or deactivated session returns 401 for both methods.
- A database failure returns a generic 503.

The save writes with `save(update_fields=["profile_type"])`, so the `UPDATE`
touches that column only. **STAFF is an affiliation label, not a permission**: it
never sets `is_staff` or `is_superuser`, adds no group or permission, and grants no
Django admin access.

## Frontend behavior

The profile panel loads `/api/profile/` on mount and refreshes it on focus, on
becoming visible, and every 60 seconds, which also keeps the CSRF token current.
Selecting an option updates only local state; **Save profile** sends the PATCH and
the button becomes a quiet **Saved** confirmation once the selection matches the
stored value. Pending, success, and error states are announced through live
regions. A 401 returns to sign-in with an expiry notice, a 403 refreshes the token
and asks for an explicit retry, and network failures show a retry message without
claiming the profile was saved. A background refresh never overwrites a selection
while a save is in flight. Sign-out and the health panel remain available.

The interface was restyled across registration, sign-in, and profile: a forest
green and warm off-white palette, serif display headings with system UI text, a
CSS/SVG campus skyline backdrop, and short staggered entrance and state
transitions. All motion is disabled under `prefers-reduced-motion`. No animation
library, external font, or image asset was added.

## Verification

```sh
.venv/bin/python backend/manage.py check
.venv/bin/python backend/manage.py migrate --check
.venv/bin/python backend/manage.py makemigrations --check --dry-run
.venv/bin/python backend/manage.py test accounts core --keepdb
npm --prefix frontend run build
```

All 48 backend tests pass against PostgreSQL (35 existing, 13 profile tests).
The profile tests cover unauthenticated and expired-session access, deactivated
accounts, reading only safe fields, saving every supported value, rejecting
unsupported values and every privilege-related field, leaving administrative flags
and other users untouched, STAFF granting no permissions, persistence across
logout and a later login, CSRF token/cookie/origin enforcement, method
restrictions, and a generic database-failure response. Django checks, migration
consistency, and the frontend build pass. `check --deploy` still reports only the
documented `security.W005` and `security.W021`.

Headless Chrome checks through the real Vite proxy also passed: registration with
validation errors and the password visibility toggle, invalid then valid sign-in,
the profile view starting at the saved value, arrow-key movement through the radio
group with a visible focus ring, saving, refresh persistence, API rejection of an
invalid value and of a privileged field, CSRF-less PATCH returning 403, sign-out
invalidating the session, signing in again with the selection intact, and an
expired session returning to sign-in. Layouts at 320, 390, 768, and 1440 pixels
have no horizontal overflow, option cards stay above the 44-pixel touch target,
and reduced motion disables entrance animations with content fully visible. No
unexpected browser console errors were observed; the only non-2xx responses were
the intended 400/401/403 probes. The harness is an ignored local artifact at
`.local/verify-profile.mjs`; no browser dependency was added. Other browser
engines, screen readers, and deployed HTTPS have not been verified.

## Manual checklist

1. Sign in. Confirm the profile view shows your email and that a new account
   starts on **Visitor** with the button reading **Saved**.
2. Choose **Student**. Since US-07 this opens **Verify your role**; complete it
   (see [US-07](verified-roles.md)) and confirm `Verified. Your affiliation is Student.`
3. Refresh; confirm **Student** is still selected. Sign out, sign in again, and
   confirm it is still **Student**.
4. Tab to the radio group and move with the arrow keys; confirm a visible focus
   ring and that Space/Enter does not submit an unintended value. Moving onto an
   unverified Student or Staff opens the dialog; confirm focus moves into it and
   returns after Escape.
5. In DevTools, `PATCH /api/profile/` with `{"profile_type":"ADMIN"}` (400),
   `{"profile_type":"STAFF","is_staff":true}` (400), `{"profile_type":"STAFF"}`
   without a staff verification (400, since US-07), and without `X-CSRFToken`
   (403). Confirm the stored value did not change.
6. Verify a profile as **Staff**, then confirm in pgAdmin or `psql` that `is_staff`
   and `is_superuser` are still `false` and that `/admin/` is not reachable.
7. Delete the session cookie, then save; confirm the expiry notice and the return
   to sign-in. Use DevTools Offline mode while saving; confirm a clear error.
8. Check the layout at a narrow width and with **Reduce motion** enabled.

Avatars, uploads, dashboards, and additional profile fields remain out of scope.
This is a first working version, not a production-ready release.
