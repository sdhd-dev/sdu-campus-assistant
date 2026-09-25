# US-05: Continue with Google and optional two-step verification

Email and password registration and login are unchanged. Sign-in adds a
**Continue with Google** button under the password form, and the profile gains a
**Sign-in and security** section where a user can connect or disconnect Google
and turn two-step verification (TOTP) on or off. Two-step verification is never
required: it is off until the user turns it on.

Migration `accounts/0002_google_and_two_factor` adds `User.google_subject` and the
`TOTPDevice` and `RecoveryCode` tables. New dependencies are pinned in
`backend/requirements.txt`: `google-auth` (ID token verification), `PyOTP`
(TOTP), and `segno` (setup QR code), with their transitive packages.

## Configuration

Google sign-in is optional. Without `GOOGLE_OAUTH_CLIENT_ID` the button is hidden
and the Google endpoints refuse requests with 404. To enable it:

1. In Google Cloud Console → **Credentials**, create an **OAuth client ID** of type
   **Web application**.
2. Add `http://127.0.0.1:5173` and `http://localhost:5173` as **Authorized
   JavaScript origins**. No redirect URI is needed: the button uses popup mode.
3. Set `GOOGLE_OAUTH_CLIENT_ID=<client id>` in `.env` and restart Django.

No client secret is used or stored.

## API

All endpoints require the CSRF cookie and `X-CSRFToken` on writes and disable caching.

| Endpoint | Behavior |
| --- | --- |
| `GET /api/auth/google/` | `client_id` (or `null` when disabled), a per-session `nonce`, and `csrf_token`. |
| `POST /api/auth/google/` | Accepts exactly `{"credential": "<Google ID token>"}`. Signs in, creates a passwordless account, or returns the 2FA challenge. |
| `POST /api/auth/two-factor/verify/` | Accepts exactly `{"code": "..."}` (authenticator or recovery code) while a sign-in is pending. Returns `email` and `csrf_token`. |
| `GET /api/auth/security/` | `google_available`, `google_linked`, `has_password`, `two_factor_enabled`, `recovery_codes_remaining`, `csrf_token`. Session required. |
| `POST /api/auth/security/google/` | Connects the Google account in `{"credential"}` to the signed-in account. |
| `DELETE /api/auth/security/google/` | Disconnects Google. Refused (400) when the account has no password. |
| `POST /api/auth/security/two-factor/setup/` | Creates an unconfirmed authenticator and returns `secret`, `otpauth_uri`, and an SVG `qr_code`. 409 when already on. |
| `POST /api/auth/security/two-factor/enable/` | `{"code"}` from the new authenticator. Turns 2FA on and returns ten recovery codes once. |
| `POST /api/auth/security/two-factor/disable/` | `{"code"}` (authenticator or recovery code). Turns 2FA off and deletes recovery codes. |

`POST /api/auth/login/` and `POST /api/auth/google/` return
`{"two_factor_required": true, "csrf_token": "..."}` instead of a session when
2FA is on. The session stays anonymous until `/two-factor/verify/` accepts a code;
the pending sign-in expires after five minutes.

## Security decisions

- **Google tokens are verified on the server** against Google's keys, the
  configured client ID (audience), issuer, and expiry. `email_verified` must be
  true. The token must carry the nonce issued to this browser session, so a token
  captured elsewhere cannot be replayed.
- **Accounts are matched by Google's `sub`**, never by email, since a Google
  email can change.
- **No automatic account joining.** If a Google email matches an existing
  account, sign-in returns 409 and the owner must sign in with the password and
  connect Google from the profile. Registration does not prove email ownership, so
  joining by email would let anyone who registered an address take over a Google
  sign-in (or the reverse).
- Accounts created by Google have no usable password and the `VISITOR` profile
  type, and never receive `is_staff` or `is_superuser`. A passwordless account
  cannot disconnect its only sign-in method.
- **TOTP codes cannot be replayed**: the last accepted 30-second step is stored and
  the device row is locked during the check. One step of clock drift either side is
  accepted.
- **Five wrong codes lock the second step for five minutes**, across all pending
  sign-ins for that account.
- **Recovery codes** are ten single-use codes; only SHA-256 digests are stored.
  Case, spaces, and dashes are ignored when entering them.
- 2FA applies to Google sign-in too.

## Logging

Two-step verification events go to the console through the `accounts.two_factor`
logger. Each line contains only the user id, the event, the `purpose`
(`sign_in`, `enable`, or `disable`), and counters. Codes, TOTP secrets,
`otpauth://` URIs, recovery codes, and email addresses are never logged. Tests check
every log line of every 2FA test for them.

| Event | Level |
| --- | --- |
| `setup_started`, `enabled`, `disabled` | INFO |
| `code_accepted` (authenticator code) | INFO |
| `code_invalid` (with attempt number) | INFO |
| `recovery_code_used` (with codes remaining) | WARNING |
| `locked` (fifth wrong code), `code_refused_locked` (attempt during lockout) | WARNING |

## Verification

```sh
.venv/bin/python backend/manage.py check
.venv/bin/python backend/manage.py makemigrations --check --dry-run
.venv/bin/python backend/manage.py migrate
.venv/bin/python backend/manage.py test accounts core --keepdb
npm --prefix frontend run build
```

All backend tests pass against PostgreSQL. Google's verifier is mocked in tests;
a real Google sign-in needs a configured client ID and has not been run end to end.

## Manual checklist

1. Without a client ID, confirm the login page has no Google button.
2. With a client ID, **Continue with Google** with a new Google account; confirm
   you land in the profile as Visitor, and **Sign-in and security** shows Google
   connected and no **Disconnect** button.
3. Sign in with a password account whose email equals your Google email; confirm
   the 409 message, then connect Google from the profile and sign in with Google.
4. **Two-step verification → Turn on**, scan the QR code, enter the code, save the
   recovery codes. Sign out and in: confirm the code step, a wrong code error,
   and a recovery code working once.
5. **Turn off…** with a current code; confirm sign-in no longer asks for one.
