# US-09: authenticator app removed

The authenticator app (TOTP), added in US-05 and kept as an optional extra in
US-08, is removed. Two-step verification is now a code sent to the account email,
with single-use recovery codes as the fallback. See the
[US-08 guide](email-two-factor.md) for how it works.

## What was removed

- **Model:** `TOTPDevice`, dropped by migration `0007_remove_authenticator_app`.
- **Endpoints:** `POST /api/auth/security/two-factor/setup/`, `…/enable/`, and
  `…/disable/` now return 404.
- **Second step:** `POST /api/auth/two-factor/verify/` accepts only `method: "email"`
  or `"recovery"`. `GET /api/auth/security/` no longer returns `totp_enabled`.
- **Interface:**
  - the **Authenticator app** item and its QR setup in **Sign-in and security**;
  - **Use your authenticator app** on the sign-in step;
  - the authenticator choice when turning two-step verification off.
- **Dependencies:** `PyOTP` and `segno` are no longer in `backend/requirements.txt`.
  Run `pip install -r backend/requirements.txt` in a fresh environment. An existing
  one can drop them with `pip uninstall pyotp segno`.

Kept:
- Recovery codes: issued when two-step verification is turned on, deleted when it
  is turned off.
- The recovery-code lockout: five wrong codes lock them for five minutes.

## Existing accounts

Migration `0007` first switches every account that was protected only by the app
to email codes, so its two-step verification stays on. It keeps the existing
recovery codes, so failed email delivery never locks the user out. Then the
migration drops the table.

This cannot be reversed: the app secrets are deleted. Rolling the migration back
recreates an empty table.

The switch was checked on the test database by rolling back to 0006, creating an
app-only account, and migrating forward: the account ended up with email codes
on. In the local development database, which already held one app-only account,
the count of email-2FA accounts did not change after the migration, and the reason
could no longer be traced once the table was gone. No account there is left with
recovery codes but without two-step verification.

## Tests

- `test_two_factor.py` is rewritten as `SecondStepTests`:
  - the pending sign-in, recovery codes, and their lockout;
  - safe response fields and log lines;
  - checks that `totp` is refused and the old endpoints return 404.
- Authenticator tests are removed from `test_email_two_factor.py`.
- The Google 2FA test now uses the email code.

All 118 backend tests pass. The US-07 and US-08 headless Chrome checks pass; the
US-08 check also asserts that no authenticator option is shown.
