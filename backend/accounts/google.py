"""Verifies Google Identity Services ID tokens ("Continue with Google")."""
import hmac

from django.conf import settings
from google.auth import exceptions as google_exceptions
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

_transport = google_requests.Request()


class InvalidGoogleCredential(Exception):
    pass


class GoogleUnavailable(Exception):
    pass


def client_id():
    return settings.GOOGLE_OAUTH_CLIENT_ID or None


def verify_credential(credential, nonce):
    """Returns Google's stable subject and verified email, or raises."""
    audience = client_id()
    if not audience or not isinstance(credential, str) or not credential or not nonce:
        raise InvalidGoogleCredential
    try:
        # Checks the signature against Google's published keys, the audience,
        # the issuer (accounts.google.com), and expiry.
        claims = id_token.verify_oauth2_token(
            credential, _transport, audience, clock_skew_in_seconds=10,
        )
    except google_exceptions.TransportError as error:
        raise GoogleUnavailable from error
    except (ValueError, google_exceptions.GoogleAuthError) as error:
        raise InvalidGoogleCredential from error
    # The nonce ties the token to this browser session, so a captured token cannot be replayed.
    if not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
        raise InvalidGoogleCredential
    subject, email = claims.get("sub"), claims.get("email")
    if not subject or not email or claims.get("email_verified") is not True:
        raise InvalidGoogleCredential
    return {
        "subject": subject,
        "email": email.strip().lower(),
        # Set only for Google Workspace accounts. Unused for now: if university mail moves to
        # Workspace, university.affiliation_for_domain(hosted_domain) could verify the status.
        # The email domain alone must never be trusted for that; only "hd" proves it.
        "hosted_domain": claims.get("hd"),
    }
