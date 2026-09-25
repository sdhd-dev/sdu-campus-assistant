"""Two-step verification: an email code (main method), an optional authenticator app,
and single-use recovery codes issued when the first method is turned on."""
import hashlib
import hmac
import logging
import re
import secrets
from datetime import timedelta

import pyotp
import segno
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from . import email_codes
from .models import RecoveryCode, TOTPDevice

User = get_user_model()

ISSUER = "SDU Campus Assistant"
MAX_FAILURES = 5
LOCKOUT = timedelta(minutes=5)
RECOVERY_CODE_COUNT = 10
# Crockford-style alphabet: no 0/O or 1/I/L to misread when typing from paper.
RECOVERY_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"

EMAIL, TOTP, RECOVERY = "email", "totp", "recovery"
OK, INVALID, LOCKED, ALREADY = "ok", "invalid", "locked", "already"
EXPIRED, NO_CODE = email_codes.EXPIRED, email_codes.NO_CODE
# Security events only: user id, event, method, and counters. Never codes, secrets, or addresses.
log = logging.getLogger("accounts.two_factor")


def _digest(code):
    return hashlib.sha256(code.encode()).hexdigest()


def _normalize_recovery(code):
    return re.sub(r"[\s-]", "", code).lower()


def _new_recovery_code():
    raw = "".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(10))
    return f"{raw[:5]}-{raw[5:]}"


def _fresh(user):
    """The user's current row; cached relations such as totp_device can be stale."""
    return User.objects.get(pk=user.pk)


def recovery_codes_remaining(user):
    return RecoveryCode.objects.filter(user=user, used_at__isnull=True).count()


def methods(user):
    """The ways this user can pass the second step, main method first."""
    user = _fresh(user)
    available = []
    if user.email_two_factor:
        available.append(EMAIL)
    if user.totp_enabled:
        available.append(TOTP)
    if user.two_factor_enabled and recovery_codes_remaining(user):
        available.append(RECOVERY)
    return available


def _matches_totp(device, code, now):
    if not re.fullmatch(r"\d{6}", code):
        return False
    totp = pyotp.TOTP(device.secret)
    current = totp.timecode(now)
    # One step either side tolerates clock drift of about 30 seconds.
    for step in (current - 1, current, current + 1):
        if device.last_used_step is not None and step <= device.last_used_step:
            continue
        if hmac.compare_digest(totp.generate_otp(step), code):
            device.last_used_step = step
            return True
    return False


def _matches_recovery(user, code, now):
    normalized = _normalize_recovery(code)
    if len(normalized) != 10:
        return False
    return RecoveryCode.objects.filter(
        user=user, code_hash=_digest(normalized), used_at__isnull=True,
    ).update(used_at=now) == 1


def check_code(user, code, *, method, purpose, confirmed=True):
    """Checks an authenticator or recovery code, with replay and lockout protection."""
    code = code.strip() if isinstance(code, str) else ""
    now = timezone.now()
    with transaction.atomic():
        # The row lock serialises concurrent attempts, so one code cannot be used twice.
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        if locked_user.two_factor_locked_until and locked_user.two_factor_locked_until > now:
            log.warning("code_refused_locked user=%s purpose=%s method=%s", user.pk, purpose, method)
            return LOCKED
        matched = False
        if method == TOTP:
            device = TOTPDevice.objects.select_for_update().filter(user=user, confirmed=confirmed).first()
            if device is not None and _matches_totp(device, code, now):
                device.save(update_fields=["last_used_step"])
                matched = True
        elif method == RECOVERY:
            matched = _matches_recovery(user, code, now)
        if matched:
            User.objects.filter(pk=user.pk).update(
                two_factor_failed_attempts=0, two_factor_locked_until=None,
            )
            if method == RECOVERY:
                log.warning("recovery_code_used user=%s purpose=%s remaining=%s",
                            user.pk, purpose, recovery_codes_remaining(user))
            else:
                log.info("code_accepted user=%s purpose=%s method=%s", user.pk, purpose, method)
            return OK
        attempts = locked_user.two_factor_failed_attempts + 1
        locked = attempts >= MAX_FAILURES
        User.objects.filter(pk=user.pk).update(
            two_factor_failed_attempts=0 if locked else attempts,
            two_factor_locked_until=now + LOCKOUT if locked else None,
        )
        log.info("code_invalid user=%s purpose=%s method=%s attempts=%s",
                 user.pk, purpose, method, attempts)
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
    return check_code(user, code, method=method, purpose=purpose)


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


def _enabled(user, method, codes):
    log.info("enabled user=%s method=%s recovery_codes=%s", user.pk, method, len(codes or ()))


def enable_email(user, code):
    """Turns on email codes once a code sent to the account email comes back, which also
    proves the address. Returns (result, recovery_codes or None)."""
    with transaction.atomic():
        fresh = User.objects.select_for_update().get(pk=user.pk)
        if fresh.email_two_factor:
            return ALREADY, None
        result, _ = email_codes.check(user, email_codes.SECURITY, code)
        if result != OK:
            return result, None
        # Recovery codes come with the first method, so failed email delivery never locks anyone out.
        first = not fresh.totp_enabled
        User.objects.filter(pk=user.pk).update(email_two_factor=True)
        codes = _issue_recovery_codes(user) if first else None
    _enabled(user, EMAIL, codes)
    return OK, codes


def start_setup(user):
    """Creates a fresh unconfirmed authenticator. Returns None if one is already on."""
    if _fresh(user).totp_enabled:
        return None
    secret = pyotp.random_base32()
    TOTPDevice.objects.update_or_create(user=user, defaults={
        "secret": secret, "confirmed": False, "last_used_step": None,
    })
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=ISSUER)
    log.info("setup_started user=%s method=totp", user.pk)
    return {
        "secret": secret,
        "otpauth_uri": uri,
        "qr_code": segno.make(uri, error="m").svg_data_uri(scale=5, border=2),
    }


def confirm_setup(user, code):
    """Turns on the authenticator once it produces a valid code.
    Returns (result, recovery_codes or None)."""
    with transaction.atomic():
        first = not _fresh(user).two_factor_enabled
        result = check_code(user, code, method=TOTP, purpose="enable", confirmed=False)
        if result != OK:
            return result, None
        TOTPDevice.objects.filter(user=user).update(confirmed=True)
        codes = _issue_recovery_codes(user) if first else None
    _enabled(user, TOTP, codes)
    return OK, codes


def _disable(user, target, method, code):
    with transaction.atomic():
        result = authorize(user, method, code, purpose="disable")
        if result != OK:
            return result
        if target == EMAIL:
            User.objects.filter(pk=user.pk).update(email_two_factor=False)
        else:
            TOTPDevice.objects.filter(user=user).delete()
        if not _fresh(user).two_factor_enabled:
            # With no method left, two-step verification is off and recovery codes go too.
            RecoveryCode.objects.filter(user=user).delete()
            email_codes.discard(user, email_codes.SIGN_IN)
    log.info("disabled user=%s method=%s authorized_by=%s", user.pk, target, method)
    return OK


def disable_email(user, method, code):
    if not _fresh(user).email_two_factor:
        return INVALID
    return _disable(user, EMAIL, method, code)


def disable_totp(user, method, code):
    if not _fresh(user).totp_enabled:
        return INVALID
    return _disable(user, TOTP, method, code)
