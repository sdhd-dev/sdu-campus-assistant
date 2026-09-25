"""Two-step verification: a code sent to the account email, with single-use recovery
codes issued when it is turned on."""
import hashlib
import logging
import re
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from . import email_codes
from .models import RecoveryCode

User = get_user_model()

MAX_FAILURES = 5
LOCKOUT = timedelta(minutes=5)
RECOVERY_CODE_COUNT = 10
# Crockford-style alphabet: no 0/O or 1/I/L to misread when typing from paper.
RECOVERY_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"

EMAIL, RECOVERY = "email", "recovery"
OK, INVALID, LOCKED, ALREADY = "ok", "invalid", "locked", "already"
EXPIRED, NO_CODE = email_codes.EXPIRED, email_codes.NO_CODE
# Security events only: user id, event, method, and counters. Never codes or addresses.
log = logging.getLogger("accounts.two_factor")


def _digest(code):
    return hashlib.sha256(code.encode()).hexdigest()


def _normalize_recovery(code):
    return re.sub(r"[\s-]", "", code).lower()


def _new_recovery_code():
    raw = "".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(10))
    return f"{raw[:5]}-{raw[5:]}"


def _fresh(user):
    """The user's current row; the request's copy can be stale."""
    return User.objects.get(pk=user.pk)


def recovery_codes_remaining(user):
    return RecoveryCode.objects.filter(user=user, used_at__isnull=True).count()


def methods(user):
    """The ways this user can pass the second step, main method first."""
    user = _fresh(user)
    available = []
    if user.email_two_factor:
        available.append(EMAIL)
    if user.email_two_factor and recovery_codes_remaining(user):
        available.append(RECOVERY)
    return available


def _matches_recovery(user, code, now):
    normalized = _normalize_recovery(code)
    if len(normalized) != 10:
        return False
    return RecoveryCode.objects.filter(
        user=user, code_hash=_digest(normalized), used_at__isnull=True,
    ).update(used_at=now) == 1


def check_code(user, code, *, purpose):
    """Checks a recovery code, with lockout protection."""
    code = code.strip() if isinstance(code, str) else ""
    now = timezone.now()
    with transaction.atomic():
        # The row lock serialises concurrent attempts, so one code cannot be used twice.
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        if locked_user.two_factor_locked_until and locked_user.two_factor_locked_until > now:
            log.warning("code_refused_locked user=%s purpose=%s method=recovery", user.pk, purpose)
            return LOCKED
        if _matches_recovery(user, code, now):
            User.objects.filter(pk=user.pk).update(
                two_factor_failed_attempts=0, two_factor_locked_until=None,
            )
            log.warning("recovery_code_used user=%s purpose=%s remaining=%s",
                        user.pk, purpose, recovery_codes_remaining(user))
            return OK
        attempts = locked_user.two_factor_failed_attempts + 1
        locked = attempts >= MAX_FAILURES
        User.objects.filter(pk=user.pk).update(
            two_factor_failed_attempts=0 if locked else attempts,
            two_factor_locked_until=now + LOCKOUT if locked else None,
        )
        log.info("code_invalid user=%s purpose=%s method=recovery attempts=%s",
                 user.pk, purpose, attempts)
        if locked:
            log.warning("locked user=%s purpose=%s minutes=%s",
                        user.pk, purpose, int(LOCKOUT.total_seconds() // 60))
        return INVALID


def authorize(user, method, code, *, purpose):
    """Checks a second-step code by any method this user has. purpose is "sign_in" or
    "disable". Email codes answer EXPIRED/NO_CODE, and LOCKED once burned."""
    if method not in methods(user):
        return INVALID
    if method == EMAIL:
        email_purpose = email_codes.SIGN_IN if purpose == "sign_in" else email_codes.SECURITY
        result, _ = email_codes.check(user, email_purpose, code)
        if result == OK:
            log.info("code_accepted user=%s purpose=%s method=email", user.pk, purpose)
        return result
    return check_code(user, code, purpose=purpose)


def send_code(user, *, sign_in):
    """Emails a code to the account address. Returns (result, retry_after); may raise
    email_codes.MailUnavailable."""
    purpose = email_codes.SIGN_IN if sign_in else email_codes.SECURITY
    return email_codes.issue(user, purpose, user.email)


def _issue_recovery_codes(user):
    codes = [_new_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
    RecoveryCode.objects.filter(user=user).delete()
    RecoveryCode.objects.bulk_create(
        RecoveryCode(user=user, code_hash=_digest(_normalize_recovery(value))) for value in codes
    )
    return codes


def enable_email(user, code):
    """Turns on email codes once a code sent to the account email comes back, which also
    proves the address. Returns (result, recovery_codes)."""
    with transaction.atomic():
        fresh = User.objects.select_for_update().get(pk=user.pk)
        if fresh.email_two_factor:
            return ALREADY, None
        result, _ = email_codes.check(user, email_codes.SECURITY, code)
        if result != OK:
            return result, None
        User.objects.filter(pk=user.pk).update(email_two_factor=True)
        # Recovery codes, so failed email delivery never locks anyone out.
        codes = _issue_recovery_codes(user)
    log.info("enabled user=%s method=email recovery_codes=%s", user.pk, len(codes))
    return OK, codes


def disable_email(user, method, code):
    """Turns two-step verification off, confirmed by an email or recovery code."""
    if not _fresh(user).email_two_factor:
        return INVALID
    with transaction.atomic():
        result = authorize(user, method, code, purpose="disable")
        if result != OK:
            return result
        User.objects.filter(pk=user.pk).update(email_two_factor=False)
        RecoveryCode.objects.filter(user=user).delete()
        email_codes.discard(user, email_codes.SIGN_IN)
    log.info("disabled user=%s method=email authorized_by=%s", user.pk, method)
    return OK
