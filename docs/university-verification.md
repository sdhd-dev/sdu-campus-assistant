# US-06: university status by email code

The profile gains a **University status** section. A user enters an address on an
SDU domain, receives a 6-digit code, and enters it. The account is then marked
**Verified Student** or **Verified Staff** by the address's domain.

The verified status is separate from the self-selected `profile_type`
(Student / Staff / Visitor), which is never changed. Visitor needs no verification.
Like `profile_type`, the verified status grants no Django permissions.

Migration `accounts/0003_university_email_verification` adds four fields to the
user: `verified_affiliation`, `university_email`, `affiliation_verified_at`, and
`affiliation_source`. It also adds the `UniversityEmailChallenge` and
`UniversityEmailSend` tables. No dependencies were added. Email goes through
Django's built-in mail backends.

## Configuration

All values go in `.env` (development) or the process environment (production).
`.env.example` lists them, empty and with comments.

| Variable | Meaning |
| --- | --- |
| `UNIVERSITY_STUDENT_DOMAINS` | Comma-separated exact domains that verify **Student**. |
| `UNIVERSITY_STAFF_DOMAINS` | Comma-separated exact domains that verify **Staff**. |
| `EMAIL_BACKEND` | Empty in development, so codes print in the `runserver` terminal. `django.core.mail.backends.smtp.EmailBackend` for Gmail or other SMTP. |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS` | SMTP server; port defaults to 587 and TLS to on. |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP login. |
| `DEFAULT_FROM_EMAIL` | Sender, e.g. `SDU Campus Assistant <you@gmail.com>`. |

Domain rules:
- Domains are matched exactly and ignore case. `sdu.edu.kz` does not match
  `x.sdu.edu.kz`, and a leading `@` is ignored.
- A domain listed as both Student and Staff stops the server from starting.
- With both lists empty, the section is hidden and the API returns 404.

In production, configured domains also require the SMTP backend and non-empty
`EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, and `DEFAULT_FROM_EMAIL`.

### Demo with Gmail

1. Turn on 2-Step Verification for the Gmail account that will send codes.
2. Create an app password at <https://myaccount.google.com/apppasswords>.
3. Set the following in `.env`:
   ```
   EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
   EMAIL_HOST=smtp.gmail.com
   EMAIL_PORT=587
   EMAIL_USE_TLS=true
   EMAIL_HOST_USER=<the Gmail address>
   EMAIL_HOST_PASSWORD=<the 16-character app password>
   DEFAULT_FROM_EMAIL=SDU Campus Assistant <the same Gmail address>
   ```
4. Restart Django. Send a code to a real SDU address and check that it arrives:
   university filters may put it in spam.

Gmail limits sending to roughly 500 messages a day. That is enough for a demo, not
for production.

## API

Every endpoint requires a session. Writes require the CSRF cookie and `X-CSRFToken`.
Every response, including refusals, carries the current state and disables caching.

| Endpoint | Behavior |
| --- | --- |
| `GET /api/profile/verification/` | State: `verified_affiliation`, `university_email`, `verified_at`, `pending_email`, `resend_in` (seconds), `student_domains`, `staff_domains`, `csrf_token`. |
| `POST /api/profile/verification/start/` | Exactly `{"email"}` on a configured domain (400 otherwise). Returns 200 with `detail`: "If this address can be verified, we sent a 6-digit code to it." Returns 429 with `retry_after` when a limit applies, and 503 when sending fails. |
| `POST /api/profile/verification/confirm/` | Exactly `{"code"}`. Returns 200 with the verified state. Refusals: 400 for a wrong, expired, or missing code; 429 after too many wrong codes; 409 when the address is already verified for another account. |
| `POST /api/profile/verification/cancel/` | Drops the pending code. |
| `DELETE /api/profile/verification/` | Removes the verified status and frees the address for other accounts. |

## Security decisions

- **The code** is 6 digits from `secrets` and lives 10 minutes. It works once, and a
  new request replaces the previous code.
- **Only a keyed digest is stored**: HMAC-SHA256 with `SECRET_KEY`, bound to the
  account and address. A plain hash of a 6-digit code could be reversed from a
  leaked database in moments.
- **Five wrong codes burn the code**. The user must request a new one.
- **Send limits**: at most one code per 60 seconds, and five per hour both per
  account and per address. The per-address limit counts requests from any account,
  so nobody can flood someone else's inbox. Send records keep only a keyed digest
  of the address and are pruned after an hour.
- **Start does not reveal who owns an address.** If the address is already verified
  for another account, no email is sent, but the response is identical. The final
  check is on confirm: a case-insensitive unique constraint on `university_email`
  means that if two accounts receive codes for one address, only the first confirm
  succeeds and the second gets 409.
  - Known limit: with real SMTP, a withheld send answers faster than a real one,
    because no mail is sent. Hiding that would need a background queue.
  - Known limit: someone can use up an address's hourly limit, delaying its owner
    by up to an hour.
- **Domains are re-checked on confirm**, in case settings changed after the code
  was sent.
- **No automatic verification from the account email.** Registration does not
  prove email ownership, so only a code proves it.

## Logging

Events go to the console through the `accounts.verification` logger. Each line has
the user id and a masked address (`a***@stu.sdu.edu.kz`). Codes and full addresses
are never logged. For send failures, only the exception type is logged, because
SMTP error text can contain the address.

| Event | Level |
| --- | --- |
| `code_sent`, `code_withheld` (address verified for another account) | INFO |
| `code_rate_limited` | WARNING |
| `code_send_failed` | ERROR |
| `code_invalid` (with attempt number), `code_expired` | INFO |
| `code_locked` (attempts exhausted) | WARNING |
| `verified`, `verification_removed` | INFO |
| `verification_conflict`, `verification_refused` (domain no longer configured) | WARNING / INFO |

With the console backend in development, the email itself, including the code,
is printed in the `runserver` terminal. That is the mail, not a log line.

## Later: Google Workspace

If SDU mail turns out to be Google Workspace, Continue with Google could set the
status without a code. The groundwork:

- `google.verify_credential` already returns `hosted_domain`, the `hd` claim, from
  the verified token.
- `university.affiliation_for_domain()` maps a domain to Student or Staff for both paths.
- `affiliation_source` already has a `GOOGLE_WORKSPACE` value.

Only `hd` proves an account belongs to the Workspace. The email domain alone must
never be trusted, because a personal Google account can use any address. Nothing
is wired into sign-in yet.

## Verification

```sh
.venv/bin/python backend/manage.py check
.venv/bin/python backend/manage.py makemigrations --check --dry-run
.venv/bin/python backend/manage.py migrate
.venv/bin/python backend/manage.py test accounts core --keepdb
npm --prefix frontend run build
```

All 103 backend tests pass against PostgreSQL, 22 of them for this story. They
cover:
- the feature switch, session, and CSRF
- exact domains and input rejection
- digest-only storage
- the identical answer and no email for an address verified elsewhere
- per-account and per-address send limits
- mail failure recording nothing
- Student and Staff results, with `profile_type` and permissions unchanged
- single use, expiry, and replacement on resend
- lockout after five wrong codes
- the confirm race returning 409
- removal of a domain from settings
- cancel and removal
- no code or full address in any log line
- the `hd` groundwork

A headless Chrome run through the Vite proxy (`.local/verify-university.mjs`,
ignored) checked:
- a rejected non-university address
- sending a code and the resend countdown
- a wrong code, then the right code, giving Verified Student with the chosen
  affiliation unchanged
- persistence after reload
- no horizontal overflow at 320 px
- removal
- clean logs

Real SMTP delivery has not been tested.

## Manual checklist

1. Set `UNIVERSITY_STUDENT_DOMAINS` and `UNIVERSITY_STAFF_DOMAINS`, leave
   `EMAIL_BACKEND` empty, and restart Django.
2. In the profile, enter a non-SDU address and confirm the error. Enter an SDU
   address, copy the code from the terminal, and confirm the **Verified** badge.
   The affiliation radio must not change.
3. Enter a wrong code five times and confirm you must request a new one. Try
   **Resend** before the countdown ends.
4. From a second account, request a code for the same address and confirm no email
   is printed but the page looks the same.
5. **Remove** the status and confirm the second account can now verify the address.
