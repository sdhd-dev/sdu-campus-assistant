# Architecture and security decisions

The browser runs a React interface built by Vite. During development it requests
relative URLs `/api/health/` and `/api/auth/register/`; Vite forwards `/api` to
Django REST Framework.
Django queries PostgreSQL through its ORM/driver. Keeping database credentials
in the backend means they never enter browser JavaScript. No `VITE_*` secret is
needed. A same-origin production router should preserve the same `/api` contract,
so broad CORS exceptions are unnecessary.

## Dependencies and isolation

Django 5.2 LTS has extended support through April 2028, and DRF 3.16 supports
Django 5.2. Python packages, including transitive dependencies, are pinned in
`backend/requirements.txt`; npm's full dependency tree is committed in
`frontend/package-lock.json`. Use `npm ci` for reproducible installs. Review and
update pins for security fixes; pinning alone does not keep dependencies secure.
`.venv` isolates project packages from the system Python.

References: [Django supported versions](https://www.djangoproject.com/download/),
[DRF 3.16 support](https://www.django-rest-framework.org/community/3.16-announcement/),
[Vite requirements](https://vite.dev/guide/).

## User model foundation

`accounts.User` extends Django's `AbstractUser`, removes `username`, and uses a
unique email for authentication. The manager normalizes email to lowercase and
supports case-insensitive lookup. PostgreSQL also enforces a case-insensitive
unique constraint, so code paths that bypass the manager cannot create accounts
that differ only by email case. This project deliberately treats the whole email
address as case-insensitive.

`AUTH_USER_MODEL` is set before the initial migration. Future relationships should
reference `settings.AUTH_USER_MODEL`, and runtime code should use
`get_user_model()`. Changing the user model after other tables depend on it is
significantly harder.

Passwords use Django's `set_password`/`check_password`, which store salted hashes;
no custom encryption or plaintext password storage is introduced. A missing
password creates an unusable password. Django's standard password validators are
configured and explicitly called by the registration serializer with the proposed
user, including email similarity checks. Model-manager methods alone do not
enforce password policy. Future password-reset flows must also validate passwords.

`profile_type` describes a campus affiliation: `STUDENT`, `STAFF`, or `VISITOR`.
It defaults to `VISITOR`, and a database constraint rejects other values.
**STAFF does not grant Django `is_staff` or `is_superuser`.** Those flags retain
their independent Django meanings. Future public serializers must exclude those
privilege flags and must not use affiliation as proof of authorization. Affiliation
verification and access policy belong to later user stories.

US-02 exposes registration at `/api/auth/register/`. It accepts only email,
password, and password confirmation. Login/logout, profile, and admin HTTP routes
remain outside the current scope. Registration creates a user without logging in
or issuing an authentication token. See [the registration guide](registration.md).

## Configuration boundaries

Shared settings default to `DEBUG=False` and require database credentials and a
secret key. Only development loads the ignored root `.env` and enables debug
output. Keep the development server bound to loopback because debug error pages
can reveal internal information.

Production imports shared settings directly, requires an explicit host allowlist
and a strong secret, enables HTTPS redirects, secure cookies, HSTS for its own
host, and verifies the PostgreSQL server certificate and hostname. It does not
inherit local hosts, local credentials, disabled database TLS, or development
debug settings. HSTS is not extended to all subdomains or preloaded because that
would require control of the whole domain and a separate deployment decision.

Do not blindly trust forwarded HTTPS headers. If HTTPS terminates at a reverse
proxy, deployment configuration must set `SECURE_PROXY_SSL_HEADER` only after
ensuring that the trusted proxy strips client-supplied forwarding headers and
that clients cannot bypass it. Otherwise HTTPS detection can be spoofed. CSRF,
session, clickjacking, and security middleware remain enabled. Future DRF views
default to requiring authentication; health and registration explicitly allow
anonymous access. Registration extends DRF session authentication to enforce
CSRF even for anonymous POST requests. A GET supplies a masked CSRF token and
sets the CSRF cookie without creating a login session. Development trusts only
the two explicit Vite origins (`http://127.0.0.1:5173` and
`http://localhost:5173`) because the existing proxy rewrites Host while preserving
the browser Origin. Production inherits neither exception and uses same-origin
routing. CSRF middleware and the Vite proxy remain enabled; no CORS package or
permissive origin rule is added.

## Database and health endpoint

The local cluster lives under ignored `.local/postgres`, listens only on
`127.0.0.1:55432`, and uses SCRAM password authentication for TCP connections.
The app role owns the project database but has no superuser, role-creation, or
database-creation privilege. The operating-system user administers this dedicated
cluster over a peer-authenticated socket. Unrelated PostgreSQL installations and
databases are untouched. Production can further separate migration and runtime
roles when deployment needs are known.

`GET /api/health/` is a small readiness check: it executes `SELECT 1`, returning
HTTP 200 with `{"status":"ok"}` or HTTP 503 with `{"status":"unavailable"}`
on database errors. It disables caching and never returns exception strings or
internal configuration. The frontend checks both the HTTP status and JSON body,
handles request cancellation/timeouts, and allows a retry after failure.
