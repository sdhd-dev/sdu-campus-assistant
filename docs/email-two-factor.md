# US-08: two-step verification by email code

The main way to use two-step verification is now a 6-digit code sent to the
account email:
- It is turned on and off in **Sign-in and security** in the profile.
- When it is on, every sign-in, by password or by **Continue with Google**, sends
  a code, and the session stays anonymous until a code is accepted.
- The authenticator app from US-05 remains as an optional extra method.
- Recovery codes come with whichever method is turned on first. If email delivery
  fails, the user can still sign in with one.

## Rules

Email codes use the shared `accounts/email_codes.py` module from US-07, with the
same rules as role verification:
- A code lives 10 minutes and works once.
- It is stored only as an HMAC keyed with `SECRET_KEY`.
- Five wrong attempts burn the code, and a new one must be sent.
- Sends are limited to one per 60 seconds and five per hour.
- Logs have no code and no full address.

Sign-in codes (`sign_in`) and codes for security changes (`security`) are
separate purposes, so a code from a sign-in email cannot turn two-step
verification off.

Other decisions:
- **Turning email codes on needs a code from the account email.** Registration
  does not prove the address, so this step does, and nobody can lock themselves
  out with a typo.
- **Recovery codes.** Ten single-use codes are issued when the first method (email
  or app) is turned on. Turning on the second method keeps them. Turning off the
  last method deletes them.
- **Turning a method off** must be confirmed with any method the user has: an
  email code (`security`), an authenticator code, or a recovery code.
- **The pending sign-in lasts 10 minutes**, up from 5, to match the email code.
- **Lockout for app and recovery codes** is now on the user, not the
  authenticator device, so it also covers recovery codes when there is no app:
  five wrong codes lock them for five minutes. Email codes are burned by their
  own rule instead.
- A rate-limited or failed send at sign-in does not block the sign-in step. The
  page offers **Resend** and the other methods.

Migration `0006_email_two_factor` adds:
- `User.email_two_factor`
- `User.two_factor_failed_attempts` and `User.two_factor_locked_until`, replacing
  the lockout fields on `TOTPDevice`

## API

| Endpoint | Behavior |
| --- | --- |
| `POST /api/auth/login/`, `POST /api/auth/google/` | With two-step verification on, the response is `{"two_factor_required": true, "methods", "email_hint", "email_code_sent", "resend_in", "csrf_token"}`. `methods` lists `email`, `totp`, and `recovery` as available, main method first; with `email` a code is sent immediately. `email_hint` is masked (`o***@gmail.com`). |
| `POST /api/auth/two-factor/verify/` | Exactly `{"method", "code"}`. The method must be one the user has. Email refusals: 400 wrong/expired/"Request a new code first", 429 after five wrong codes. App/recovery refusals: 400, or 429 during the lockout. |
| `POST /api/auth/two-factor/resend/` | Sends a new sign-in code while the step is pending; 429 with `resend_in` during the cooldown. |
| `GET /api/auth/security/` | Adds `email_two_factor_enabled`, `totp_enabled`, `email`, `email_code_pending`, and `email_resend_in`. `two_factor_enabled` now means "any method is on". |
| `POST /api/auth/security/two-factor/email/code/` | Sends a `security` code to the account email. |
| `POST /api/auth/security/two-factor/email/enable/` | `{"code"}` from that email. Returns the state plus `recovery_codes`: a list if this is the first method, otherwise `null`. 409 when already on. |
| `POST /api/auth/security/two-factor/email/disable/` | `{"method", "code"}`. |
| `POST /api/auth/security/two-factor/setup/`, `…/enable/` | Authenticator app, as in US-05. Setup is allowed while email codes are on; `recovery_codes` is `null` unless the app is the first method. |
| `POST /api/auth/security/two-factor/disable/` | Removes the app; now takes `{"method", "code"}`. |

## Logging

`accounts.two_factor` lines now carry `method=email|totp` (and `authorized_by=` on
`disabled`). Email-code events come from the shared module with
`purpose=sign_in|security` and a masked address:
- `code_sent`
- `code_rate_limited`
- `code_send_failed`
- `code_invalid`
- `code_expired`
- `code_locked`

No code, TOTP secret, recovery code, or full address appears. Tests check every
line of every 2FA test.

## Test and acceptance changes

Changed US-05 tests:
- `test_two_factor.py`: the second step sends `{method, code}`; the challenge and
  security responses have new fields; a pending sign-in expires after 600 s
  instead of 300 s; log lines include `method=`.
- `test_google.py`: the 2FA challenge now carries `methods`.

New in `test_email_two_factor.py` (17 tests):
- Turning on needs an account-email code and returns recovery codes.
- Session and CSRF are required.
- Password and Google sign-in need the email code.
- A code expires and works once; five wrong codes burn it.
- Resend is rate-limited and needs a pending sign-in.
- If mail fails, a recovery code still works.
- An unavailable method is refused.
- The app is an extra method and keeps the recovery codes, in either order.
- Turning off works with an email code or a recovery code.
- A sign-in code cannot authorise turning off.
- Removing the app keeps email codes.
- Logs contain no codes or addresses.

All 126 backend tests pass. The US-05 acceptance checklist steps 4–5 are replaced
by the checklist below.

Headless Chrome through the Vite proxy (`.local/verify-email-2fa.mjs`, ignored)
checked:
- Turning on by an email code and seeing 10 recovery codes.
- Adding the app with no new codes and "10 of 10 left".
- Signing in:
  - with the email code after a wrong one, with the resend countdown visible;
  - with the app;
  - with a recovery code, leaving "9 of 10".
- Turning email off with an email code while the app keeps 2FA on.
- Removing the app, which turns 2FA off and signs in without a step.
- No overflow at 320 px, and no leaks across 54 log lines.

Real SMTP delivery is still untested.

## Manual checklist

1. In **Sign-in and security**, **Two-step verification → Turn on**. Take the code
   from the Django terminal (console backend) and enter it. Save the recovery codes.
2. Sign out and sign in (password, then Google). Confirm the step says "We sent a
   6-digit code to u***@…", a wrong code is refused, **Resend** counts down, and
   the right code signs you in.
3. **Authenticator app → Set up**, scan, and enter a code. Confirm no new recovery
   codes. Sign in with **Use your authenticator app**.
4. Sign in with **Use a recovery code**; confirm "9 of 10 recovery codes left".
5. **Turn off…** email codes with **Email code → Send code**. Then **Remove…** the
   app with an app code. Confirm "Two-step verification is off" and that sign-in
   no longer asks for a code.
