import os
from pathlib import Path

from dotenv import load_dotenv

# Exported environment variables take precedence over the local development file.
load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=False)

from .base import *  # noqa: E402,F403

DEBUG = True
# Without an explicit backend, verification emails are printed in the runserver terminal.
if not os.environ.get("EMAIL_BACKEND", "").strip():
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
# Vite preserves the browser Origin while proxying the Host to Django.
CSRF_TRUSTED_ORIGINS = ["http://127.0.0.1:5173", "http://localhost:5173"]
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]
DATABASES["default"]["OPTIONS"]["sslmode"] = os.environ.get("POSTGRES_SSLMODE", "disable")
