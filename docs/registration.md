# US-02: email registration

US-02 adds account creation to the US-01 foundation. It does not implement login,
logout, automatic login, email verification, or profile selection. New users retain
`profile_type=VISITOR`, `is_staff=false`, and `is_superuser=false`.

## API contract

All browser requests use the relative URL **`/api/auth/register/`** through the
existing Vite `/api` proxy. Production must route `/api` on the same HTTPS origin.

1. `GET /api/auth/register/` returns HTTP 200 with `csrf_token` (a masked CSRF
   token) and `password_requirements` (a list of help strings from Django's actual
   configured validators). It sets the `csrftoken` cookie and uses `Cache-Control:
   no-store`. It does not create a user or an authenticated session.
2. `POST /api/auth/register/` requires that cookie, the token in `X-CSRFToken`,
   and a JSON object with exactly these allowed fields:

   ```json
   {
     "email": "Student@SDU.edu.kz",
     "password": "a unique password chosen by the user",
     "password_confirmation": "a unique password chosen by the user"
   }
   ```

3. Success returns **201** with only `{"email":"student@sdu.edu.kz"}`. No
   password, hash, administrative flags, profile data, session, or authentication
   token is returned. The React page clears both passwords and focuses its success
   heading. It explicitly explains that the user has not been signed in.

| Status | Behavior |
| --- | --- |
| 400 | Missing, invalid, mismatched, duplicate, or unexpected fields. Errors are arrays keyed by field; unexpected fields use `non_field_errors`. |
| 403 | Missing/invalid CSRF token or untrusted request origin. The UI refreshes its security configuration and asks the user to retry. |
| 405 | Unsupported HTTP method. GET prepares the form; POST creates the account. |
| 503 | Database failure, with a generic message and no internal exception details. |

Example validation response:

```json
{"password_confirmation":["Passwords do not match."]}
```

Only `email`, `password`, and `password_confirmation` are accepted, and all must be
strings. Additional fields are rejected, including `is_staff`, `is_superuser`,
`groups`, `user_permissions`, and `profile_type`; they are never silently ignored.

Email is trimmed and lowercased in full, matching the US-01 manager policy. Its
maximum length is 254 characters. Duplicate email checks are case-insensitive.
The initial migration already provides both `email` uniqueness and the
`accounts_user_email_ci_unique` expression constraint on `Lower(email)`. **No new
migration is needed.** An atomic insert and handling of the two email uniqueness
constraints also cover competing requests that both pass the initial lookup.

Django currently requires at least eight characters, rejects common passwords,
rejects entirely numeric passwords, and rejects passwords too similar to the
user's email/personal information. The API additionally limits passwords to 128
characters to bound input processing. Password whitespace is preserved exactly;
confirmation must match exactly. Passwords are hashed through the existing
`User.objects.create_user()` and Django `set_password()`. Application code does
not log request bodies, passwords, or password hashes.

## Request flow

```text
React form
  → same-origin GET /api/auth/register/ through Vite
  ← CSRF cookie + masked token + configured password instructions
  → POST JSON + X-CSRFToken through Vite
  → Django/DRF: CSRF and origin check
  → explicit serializer fields, email normalization, confirmation/password validation
  → existing User manager: set_password(), atomic ORM insert
  → PostgreSQL: email uniqueness constraints + persisted account
  ← HTTP 201 with normalized email only
React clears passwords, announces success, and focuses the success heading
```

A duplicate lookup is a convenience for normal validation errors; PostgreSQL is
responsible for uniqueness under concurrency. Backend tests force two requests
past the lookup together and verify one 201, one 400, and exactly one stored user.

Client validation runs on blur and submit for required values, email syntax,
length bounds, and confirmation. Django remains authoritative for password policy
and email validity. Failed requests retain values. A synchronous in-flight guard,
disabled submit button, and read-only inputs prevent overlapping submissions.
Configuration requests time out after eight seconds; registration after fifteen.
A timeout may occur after the server commits, so the UI explains that the account
may already exist. It never retries account creation automatically.

The original PostgreSQL-aware health endpoint is unchanged. Its React panel is
available in the footer and through the **Service status** link.

## Start locally

From the repository root, reuse the US-01 `.env`, virtual environment, frontend
installation, and dedicated PostgreSQL cluster. See the README for first-time
setup; do not initialize an existing cluster again.

```sh
export PATH="/Library/PostgreSQL/16/bin:$PATH"
pg_ctl -D "$PWD/.local/postgres" status
# Only if the cluster is stopped:
pg_ctl -D "$PWD/.local/postgres" -l "$PWD/.local/postgres.log" -o '-h 127.0.0.1 -p 55432 -k /tmp' start
source .venv/bin/activate
python backend/manage.py migrate
python backend/manage.py runserver 127.0.0.1:8000
```

In a second terminal, from the repository root:

```sh
npm --prefix frontend run dev
```

Visit **http://127.0.0.1:5173**. Use that host consistently during a test session
so cookies and the CSRF token share an origin.

## Test commands and results

From the repository root, with PostgreSQL running and the dedicated test database
from the README already created:

```sh
source .venv/bin/activate
python backend/manage.py check
python backend/manage.py test accounts core --keepdb
python backend/manage.py makemigrations --check --dry-run
python backend/manage.py migrate --check
npm --prefix frontend run build
```

Validation during implementation:

- Django system check: passed.
- All 22 backend tests: passed against PostgreSQL, including concurrent inserts,
  hashing, all four password validators, malformed/missing input, exact password
  whitespace, email normalization, privilege-field rejection, CSRF enforcement,
  safe responses, database failure, no login, and existing health/model behavior.
- Migration consistency: no changes detected; no unapplied migrations.
- Vite production build: passed.
- Headless Chrome through the real Vite proxy: live registration, server password
  rejection, case-insensitive duplicate rejection, and no session cookie passed.
- Browser checks: 320, 390, 768, and 1440 CSS-pixel widths without horizontal
  overflow; mobile single column; keyboard navigation, visible focus, visibility
  toggles, blur/submission errors, focus after errors/success, pending state,
  duplicate-submit prevention, reduced motion, configuration retry, and health
  retry passed. Simulated network, HTTP 503, malformed JSON, and CSRF failures
  preserved values and recovered. No browser JavaScript errors were observed.
- Color calculations: supporting text is at least 5.62:1 against its backgrounds;
  main text is 13.81:1; button text is at least 6.30:1; error text is 7.16:1;
  input borders are 3.16:1 against white. Focus outlines exceed 3:1.

The browser harness and screenshots are local artifacts under ignored `.local/`;
no browser dependency was added to the application. Actual screen-reader speech,
Safari/Firefox, physical mobile devices, and a deployed HTTPS environment have not
been verified. Browser automation checked live-region markup and focus behavior;
this is not a complete accessibility audit.

## Manual review

1. Load the page at desktop and mobile widths. Confirm the two-column desktop
   layout becomes one column, labels remain visible, and the form does not overflow.
2. Tab from **Skip to registration** through email, password, its visibility
   toggle, confirmation, its toggle, and **Create account**. Toggle passwords with
   Space or Enter. Check visible focus and OS reduced-motion behavior.
3. Type an incomplete email. Confirm no error appears while first typing; blur to
   see its error. Submit empty fields and confirm focus moves to the first invalid
   input. Enter different passwords and check the confirmation error.
4. Submit a short, common, all-numeric, or email-similar password. Confirm Django's
   error appears beside Password and entered values remain available for correction.
5. Register a new email with a unique password. With DevTools network throttling,
   verify **Creating account…**, its subtle static progress indicator, and disabled
   resubmission. On success, confirm the normalized email, success focus, and no
   automatic login or password fields. The indicator does not run a looping animation.
6. Reload and reuse the email with different capitalization or surrounding spaces.
   Confirm the email error and unchanged account count in pgAdmin.
7. Stop Django after the form has loaded, then submit. Confirm a clear general
   failure and preserved inputs. Restart Django and retry. Reload while Django is
   stopped to check configuration failure and **Try again** recovery.
8. Check **Service status** and **Check again**. Its existing healthy/error behavior
   must still work. In DevTools, POSTs must contain `X-CSRFToken`; removing it must
   produce 403. Additional fields such as `is_staff: true` must produce 400.

## Inspect the account in pgAdmin

Register a server connection using the values in your private root `.env`:

- Host: `127.0.0.1`; port: `55432` for the README's local cluster.
- Maintenance database: `sdu_campus_assistant`.
- Username: `sdu_campus_app`; password: your `POSTGRES_PASSWORD`.
- Local SSL mode: disabled, matching the local configuration. Remote deployments
  require certificate verification, as described in the README.

Navigate to **Databases → sdu_campus_assistant → Schemas → public → Tables →
accounts_user** and open **Query Tool**. Replace the example email with yours:

```sql
SELECT id, email, profile_type, is_staff, is_superuser, is_active, last_login
FROM accounts_user
WHERE lower(email) = lower('your-test-email@example.com');
```

Expect one row, a lowercase email, `VISITOR`, `is_staff=false`,
`is_superuser=false`, `is_active=true`, and `last_login=NULL`. To verify empty
permissions and that a hash was stored without displaying the hash:

```sql
SELECT u.email,
       u.password LIKE 'pbkdf2_sha256$%' AS uses_default_password_hash,
       NOT EXISTS (SELECT 1 FROM accounts_user_groups g WHERE g.user_id = u.id)
         AS has_no_groups,
       NOT EXISTS (SELECT 1 FROM accounts_user_user_permissions p WHERE p.user_id = u.id)
         AS has_no_direct_permissions
FROM accounts_user u
WHERE lower(u.email) = lower('your-test-email@example.com');
```

All three Boolean results should be true with the current default hasher. Avoid
copying password hashes into screenshots, logs, or review comments. The browser
verification created `us02-browser-1789696924410@example.com` as a local review
account; it has no administrative privileges.

## Changed files

- `backend/accounts/serializers.py`: explicit registration fields, validation, manager
  creation, and race-safe duplicate handling.
- `backend/accounts/views.py`: public CSRF-protected registration and configuration.
- `backend/accounts/tests.py`: API, security, persistence, and concurrency tests.
- `backend/config/urls.py`: registration route, preserving health.
- `backend/config/settings/development.py`: two explicit trusted Vite origins.
- `frontend/src/App.jsx`: SDU page shell, introduction, and service-status access.
- `frontend/src/RegistrationForm.jsx`: real API integration and accessible form states.
- `frontend/src/ServiceStatus.jsx`: existing health UI extracted into a component.
- `frontend/src/style.css`: responsive palette, spacing, focus, and reduced motion.
- `frontend/index.html`: theme color aligned with the requested primary color.
- `README.md`, `docs/architecture.md`, `docs/registration.md`: behavior and handoff.

## Scope and limitations

There is no email ownership verification, SDU-domain restriction, registration
rate limiting, login/logout, profile selection, or production deployment in this
story. A duplicate error reveals whether an email is registered, as required for
this form's feedback. Abuse controls and email verification require follow-up
product decisions before public deployment. Success is an in-memory page state;
reloading displays a new registration form. No commits or pushes are part of this
handoff.
