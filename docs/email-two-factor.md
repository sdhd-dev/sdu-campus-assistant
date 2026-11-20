# US-08: two-step verification by email code

Two-step verification is a 6-digit code sent to the account email:
- It is turned on and off in **Sign-in and security** in the profile.
- When it is on, every sign-in, by password or by **Continue with Google**, sends
  a code, and the session stays anonymous until a code is accepted.
- Ten single-use recovery codes are issued when it is turned on. If email delivery
  fails, the user can still sign in with one.

> The authenticator app that US-08 kept as an optional extra was removed in
> [US-09](remove-authenticator.md). Email codes and recovery codes are the only
> second-step methods.

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
- **Turning on needs a code from the account email.** Registration does not prove
  the address, so this step does, and nobody can lock themselves out with a typo.
- **Recovery codes.** Ten are issued when two-step verification is turned on and
  deleted when it is turned off. Only SHA-256 digests are stored.
- **Turning off** must be confirmed with an email code (`security`) or a recovery
  code.
- **The pending sign-in lasts 10 minutes**, up from 5, to match the email code.
- **Recovery-code lockout** is on the user: five wrong recovery codes lock them for
  five minutes. Email codes are burned by their own rule instead.
- A rate-limited or failed send at sign-in does not block the sign-in step. The
  page offers **Resend** and the recovery code.

Migration `0006_email_two_factor` adds:
- `User.email_two_factor`
- `User.two_factor_failed_attempts` and `User.two_factor_locked_until`

## API

| Endpoint | Behavior |
| --- | --- |
| `POST /api/auth/login/`, `POST /api/auth/google/` | With two-step verification on, the response is `{"two_factor_required": true, "methods", "email_hint", "email_code_sent", "resend_in", "csrf_token"}`. `methods` is `["email", "recovery"]`, or `["email"]` once every recovery code is used. A code is sent immediately. `email_hint` is masked (`o***@gmail.com`). |
| `POST /api/auth/two-factor/verify/` | Exactly `{"method", "code"}` with `email` or `recovery`. Email refusals: 400 wrong/expired/"Request a new code first", 429 after five wrong codes. Recovery refusals: 400, or 429 during the lockout. |
| `POST /api/auth/two-factor/resend/` | Sends a new sign-in code while the step is pending; 429 with `resend_in` during the cooldown. |
| `GET /api/auth/security/` | `google_available`, `google_linked`, `has_password`, `two_factor_enabled`, `email_two_factor_enabled`, `recovery_codes_remaining`, `email`, `email_code_pending`, `email_resend_in`, `csrf_token`. |
| `POST /api/auth/security/two-factor/email/code/` | Sends a `security` code to the account email. |
| `POST /api/auth/security/two-factor/email/enable/` | `{"code"}` from that email. Returns the state plus ten `recovery_codes`, shown once. 409 when already on. |
| `POST /api/auth/security/two-factor/email/disable/` | `{"method", "code"}` with `email` or `recovery`. Deletes the recovery codes. |

## Logging

`accounts.two_factor` lines carry the user id, `purpose`, `method=email|recovery`,
and counters. `disabled` also carries `authorized_by=`. Email-code events come
from the shared module with `purpose=sign_in|security` and a masked address:
- `code_sent`
- `code_rate_limited`
- `code_send_failed`
- `code_invalid`
- `code_expired`
- `code_locked`

No code, recovery code, or full address appears. Tests check every line of every
2FA test.

## Test and acceptance changes

Changed US-05 tests:
- The second step sends `{method, code}`.
- The challenge and security responses have new fields.
- A pending sign-in expires after 600 s instead of 300 s.
- The Google 2FA test uses the email code.

Since US-09, `test_two_factor.py` (`SecondStepTests`) covers:
- the pending sign-in
- recovery codes and their lockout
- safe response fields
- log lines

`test_email_two_factor.py` covers:
- Turning on needs an account-email code and returns recovery codes.
- Session and CSRF are required.
- Password and Google sign-in need the email code.
- A code expires and works once; five wrong codes burn it.
- Resend is rate-limited and needs a pending sign-in.
- If mail fails, a recovery code still works.
- An unavailable method is refused.
- Turning off works with an email code or a recovery code.
- A sign-in code cannot authorise turning off.
- Logs contain no codes or addresses.

All 118 backend tests pass. The US-05 acceptance checklist steps 4–5 are replaced
by the checklist below.

Headless Chrome through the Vite proxy (`.local/verify-email-2fa.mjs`, ignored)
checked:
- Turning on by an email code and seeing 10 recovery codes.
- Signing in with the email code after a wrong one, with the resend countdown
  visible and no authenticator option.
- Signing in with a recovery code, leaving "9 of 10".
- Turning off with an email code, which removes the recovery codes.
- No overflow at 320 px, and no leaks in the logs.

Real SMTP delivery is still untested.

## Manual checklist

1. In **Sign-in and security**, **Two-step verification → Turn on**. Take the code
   from the Django terminal (console backend) and enter it. Save the recovery codes.
2. Sign out and sign in (password, then Google). Confirm the step says "We sent a
   6-digit code to u***@…", a wrong code is refused, **Resend** counts down, and
   the right code signs you in.
3. Sign in with **Use a recovery code**; confirm "9 of 10 recovery codes left".
4. **Turn off…** with **Email code → Send code**. Confirm "Two-step verification is
   off", that the recovery-code line is gone, and that sign-in no longer asks for
   a code.
