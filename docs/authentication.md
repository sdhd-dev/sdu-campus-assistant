# US-03: email login and logout

The existing registration page links to `#login`, and login links back to
`#register`. Registration still creates an account without signing in. Successful
login shows the email and a **Sign out** button using the existing page design.
No dependencies, database migrations, or profile editing were added.

## API

Requests use the existing same-origin `/api` proxy. All session responses disable
caching. Passwords and hashes are never returned.

| Endpoint | Behavior |
| --- | --- |
| `GET /api/auth/login/` | 200 with `csrf_token`; sets the CSRF cookie without signing in. |
| `POST /api/auth/login/` | Accepts only string `email` and `password`. Requires the CSRF cookie and `X-CSRFToken`. Returns 200 with `email` and the rotated `csrf_token`, plus Django's session cookie. |
| `GET /api/auth/me/` | 200 with `email` and `csrf_token` for an active authenticated user; otherwise 401. |
| `POST /api/auth/logout/` | Requires CSRF, flushes the session, clears its cookie, and returns 204. Safe to repeat after expiry. GET returns 405. |

Wrong passwords, unknown emails, and inactive accounts all return 401 with
`{"detail":"Invalid email or password."}`. Invalid input returns 400 with the
same message; malformed JSON returns DRF's parsing error. Username and extra fields
are rejected. Email lookup ignores case and surrounding whitespace; password
whitespace is preserved. Missing/invalid CSRF or an untrusted Origin returns 403,
including for anonymous login/logout. A login database failure returns generic 503.

Django's standard authentication backend rejects inactive accounts, including
accounts deactivated after login. Login rotates the session key and CSRF secret;
the frontend uses the returned token for logout. Replaying a logged-out session
cookie cannot restore access. Existing Django session expiry defaults apply
(two weeks); no custom token system was introduced.

## Frontend behavior

The page checks `/me/` on load to restore authentication. Signed-in pages also
check on focus, on becoming visible, and every 60 seconds while visible. A 401
returns to login with an expiry notice. Network/server failures show a retry
message without claiming the user signed out. Login and logout show pending
states and prevent duplicate submissions; requests time out after 15 seconds.
CSRF failures refresh the token and ask for an explicit retry. Passwords are
cleared on successful login; passwords and authentication tokens never enter
browser storage. Registration and the health panel remain available.

## Verification

```sh
.venv/bin/python backend/manage.py check
.venv/bin/python backend/manage.py test accounts core --keepdb
.venv/bin/python backend/manage.py makemigrations --check --dry-run
.venv/bin/python backend/manage.py migrate --check
npm --prefix frontend run build
```

All 35 backend tests pass against PostgreSQL (22 existing, 13 session tests).
Coverage includes successful/failed login, inactive accounts, authenticated
access, refresh via a session cookie, expiry/deactivation, session/CSRF rotation,
logout invalidation and cookie replay, method restrictions, input validation,
safe response fields, and CSRF cookie/token/origin enforcement. Django checks,
migration consistency, and the frontend build pass.

Headless Chrome checks through the real Vite proxy also passed: registration and
navigation, invalid login, pending submission guard, network/server/malformed-JSON
and CSRF recovery, refresh persistence, logout and cookie replay, cross-tab CSRF
rotation, session expiry, startup retry, health, and empty browser storage. Login
fits 320, 390, 768, and 1440 pixel widths without horizontal overflow. No browser
JavaScript errors were observed. The harness is an ignored local artifact under
`.local/verify-authentication.mjs`; no browser dependency was added. Other browser
engines and deployed HTTPS have not been verified.

## Manual checklist

1. Create an account; follow **Sign in**. Try a wrong password, then the correct
   password with mixed-case email. Confirm the generic error, then your email.
2. Refresh; confirm you remain signed in. Sign out, refresh again, and confirm
   `/api/auth/me/` returns 401.
3. Clear the session cookie in DevTools and refocus the page; confirm the expiry
   notice. Remove `X-CSRFToken` from a login/logout POST; confirm 403.
4. Use DevTools Offline mode during login/logout; confirm a clear error and retry
   after reconnecting. Check keyboard navigation, mobile layout, and **Service status**.

2FA, social/username login, password reset, and profile editing remain out of scope.
