# SDU Campus Assistant

A university team project for campus navigation, room and faculty search, campus
services, and student schedules. **US-01 provides the project and database
foundation; US-02 adds email registration; US-03 adds session-based email login
and logout.** Profile selection and campus features are not implemented.
Registration does not sign users in automatically.

## Structure

```text
backend/                 Django + Django REST Framework
  accounts/              Email-based User model, registration/session APIs, and tests
  config/settings/       Shared, development, and production settings
  core/                  Public database-aware health endpoint
  requirements.txt       Pinned Python dependencies, including transitive packages
frontend/                React + Vite, JavaScript
  src/                   Registration, login, account state, and live backend status
  package-lock.json      Reproducible frontend dependency tree
docs/                    Architecture and security decisions
.env.example             Development environment template
.venv/                   Local Python environment (ignored)
.local/                  Local database and optional Python installation (ignored)
```

## Prerequisites

- Python 3.12 (recommended; validated with 3.12.13).
- Node.js 24 LTS and npm (Node 22.12+ is also supported).
- PostgreSQL 16 or later, including `initdb`, `pg_ctl`, `psql`, `createuser`, and
  `createdb`. Install PostgreSQL separately; SQLite is not supported.
- Git. Optional: `uv` if your system Python is unavailable or broken.

On this macOS installation, PostgreSQL tools are in `/Library/PostgreSQL/16/bin`:

```sh
export PATH="/Library/PostgreSQL/16/bin:$PATH"
```

On other installations, add the actual PostgreSQL `bin` directory to `PATH`.
All commands below start at the repository root unless stated otherwise.

## 1. Python environment and configuration

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cp .env.example .env
python -c 'import secrets; print(secrets.token_urlsafe(64))'
python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Put the first generated value in `DJANGO_SECRET_KEY` and the second in
`POSTGRES_PASSWORD` in `.env`. Keep this file private. Never commit its contents.
Development loads this file; exported variables take precedence.

If your system Python cannot create a working environment, use `uv` instead of
the first three commands above:

```sh
UV_PYTHON_INSTALL_DIR="$PWD/.local/python" uv venv --python 3.12 --managed-python --seed .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
```

Use a fresh `.venv` path for this alternative; do not overwrite an environment
containing work you need to keep.

## 2. PostgreSQL setup

These commands create a **new project-owned cluster**, using the installed
PostgreSQL binaries. They do not connect to, alter, or delete other clusters.
Run as your normal operating-system user, not root. Port 55432 must be free.

```sh
initdb -D "$PWD/.local/postgres" --auth-local=peer --auth-host=scram-sha-256 --encoding=UTF8 --locale=C
pg_ctl -D "$PWD/.local/postgres" -l "$PWD/.local/postgres.log" -o '-h 127.0.0.1 -p 55432 -k /tmp' start
createuser -h /tmp -p 55432 --no-superuser --no-createdb --no-createrole --pwprompt sdu_campus_app
createdb -h /tmp -p 55432 --owner=sdu_campus_app sdu_campus_assistant
```

At the password prompt, enter the same `POSTGRES_PASSWORD` as in `.env`.
The cluster administrator is the operating-system user who ran `initdb`; local
socket administration uses peer authentication. Django connects over loopback
with the separate, password-authenticated `sdu_campus_app` role. That role owns
only the project databases and cannot create roles or databases.

Run `initdb`, `createuser`, and `createdb` **only once**. Check cluster status with:

```sh
pg_ctl -D "$PWD/.local/postgres" status
```

If a dedicated project database already exists elsewhere, skip cluster creation
and set the `POSTGRES_*` values in `.env` for that database. Never point migrations
at an unrelated database. Local-only development uses `POSTGRES_SSLMODE=disable`;
remote connections should use certificate verification.

## 3. Migrations and frontend installation

```sh
source .venv/bin/activate
python backend/manage.py check
python backend/manage.py migrate
python backend/manage.py makemigrations --check --dry-run
npm --prefix frontend ci
```

`AUTH_USER_MODEL=accounts.User` is configured before the first migration. Use the
committed migration; do not create Django's default user tables first.

## 4. Start development

Start PostgreSQL if stopped (from the repository root):

```sh
export PATH="/Library/PostgreSQL/16/bin:$PATH" # Adapt for your installation.
pg_ctl -D "$PWD/.local/postgres" -l "$PWD/.local/postgres.log" -o '-h 127.0.0.1 -p 55432 -k /tmp' start
```

Terminal 1, from the repository root:

```sh
source .venv/bin/activate
python backend/manage.py runserver 127.0.0.1:8000
```

Terminal 2, from the repository root:

```sh
npm --prefix frontend run dev
```

Open **http://127.0.0.1:5173** to create an account. See the
[US-02 API and manual verification guide](docs/registration.md) for registration
behavior, pgAdmin checks, changed files, and validation results.
Use **Sign in** to log in with an existing account. The page restores your session
after refresh and displays your email and **Sign out**. See the
[US-03 login/logout guide](docs/authentication.md) for API details and manual checks.

The **Service status** link leads to the health panel in the footer. It requests
`/api/health/` through Vite's
development proxy to Django at `127.0.0.1:8000`. It displays loading, healthy,
and error states and provides a retry button. The healthy state requires a
successful PostgreSQL query. Requests time out after eight seconds.

Stop Django/Vite with Ctrl+C. Stop only this project's PostgreSQL cluster with:

```sh
pg_ctl -D "$PWD/.local/postgres" stop -m fast
```

This retains the database files. Never commit `.local/` or delete it unless you
intend to discard this project's local data.

## Validation

Create a dedicated test database once as the cluster administrator, so the app
role does not need `CREATEDB`. Django tests write to this test database only:

```sh
createdb -h /tmp -p 55432 --owner=sdu_campus_app test_sdu_campus_assistant
source .venv/bin/activate
python backend/manage.py check
python backend/manage.py migrate --check
python backend/manage.py makemigrations --check --dry-run
python backend/manage.py test accounts core --keepdb
npm --prefix frontend run build
curl --fail http://127.0.0.1:8000/api/health/
curl --fail http://127.0.0.1:5173/api/health/
```

Both HTTP checks should return `{"status":"ok"}`. With Django stopped, retrying
on the page must show an error. With PostgreSQL stopped and Django running, the
endpoint returns HTTP 503 and `{"status":"unavailable"}`. Restart the stopped
service and click **Check again** to recover. The health endpoint returns no
credentials, database names, server versions, or exception details. Registration returns only the normalized account email; its
GET request supplies a CSRF token and password instructions.

## Production settings

Deployment is outside US-01 through US-03. See [architecture and security](docs/architecture.md).
Production must explicitly set `DJANGO_SETTINGS_MODULE=config.settings.production`
and supply `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` (comma-separated, no wildcard),
`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`,
and a trusted CA via `POSTGRES_SSLROOTCERT` or libpq's standard root certificate
location. Production always uses `verify-full`; the development
`POSTGRES_SSLMODE` value cannot weaken it.

Production does not load `.env`. Once the environment is supplied, run:

```sh
python backend/manage.py check --deploy --settings=config.settings.production
```

The deployment check reports `security.W005` and `security.W021`: HSTS is enabled
for the application host, but subdomain coverage and browser preload are left
off intentionally. Enable those only after the team controls the deployment
domain and confirms its HTTPS policy; see the architecture document.

Production requires HTTPS, a WSGI/ASGI application server, static hosting for
`frontend/dist`, and routing `/api/` to Django on the same origin. Vite's proxy is
development-only; `vite preview` is not a production server. No production
application server or deployment infrastructure is provisioned by this story.
