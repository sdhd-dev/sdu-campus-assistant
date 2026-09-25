"""Optional TOTP two-factor authentication with single-use recovery codes."""
import hashlib
import hmac
import logging
import re
import secrets
from datetime import timedelta

import pyotp
import segno
from django.db import transaction
from django.utils import timezone

from .models import RecoveryCode, TOTPDevice

ISSUER = "SDU Campus Assistant"
MAX_FAILURES = 5
LOCKOUT = timedelta(minutes=5)
RECOVERY_CODE_COUNT = 10
# Crockford-style alphabet: no 0/O or 1/I/L to misread when typing from paper.
RECOVERY_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"

OK, INVALID, LOCKED = "ok", "invalid", "locked"
# Security events only: user id, event, and counters. Never codes, secrets, or addresses.
log = logging.getLogger("accounts.two_factor")


def _digest(code):
    return hashlib.sha256(code.encode()).hexdigest()


def _normalize_recovery(code):
    return re.sub(r"[\s-]", "", code).lower()


def _new_recovery_code():
    raw = "".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(10))
    return f"{raw[:5]}-{raw[5:]}"


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


def check_code(user, code, *, allow_recovery=True, confirmed=True, purpose="sign_in"):
    """Checks an authenticator (or recovery) code, with replay and lockout protection."""
    code = code.strip() if isinstance(code, str) else ""
    now = timezone.now()
    with transaction.atomic():
        # The row lock serialises concurrent attempts, so one code cannot be used twice.
        device = TOTPDevice.objects.select_for_update().filter(
            user=user, confirmed=confirmed,
        ).first()
        if device is None:
            return INVALID
        if device.locked_until and device.locked_until > now:
            log.warning("code_refused_locked user=%s purpose=%s", user.pk, purpose)
            return LOCKED
        method = "totp" if _matches_totp(device, code, now) else None
        if method is None and allow_recovery and _matches_recovery(user, code, now):
            method = "recovery"
        if method:
            device.failed_attempts = 0
            device.locked_until = None
            device.save(update_fields=["last_used_step", "failed_attempts", "locked_until"])
            if method == "recovery":
                log.warning("recovery_code_used user=%s purpose=%s remaining=%s",
                            user.pk, purpose, recovery_codes_remaining(user))
            else:
                log.info("code_accepted user=%s purpose=%s", user.pk, purpose)
            return OK
        device.failed_attempts += 1
        attempts = device.failed_attempts
        locked = attempts >= MAX_FAILURES
        if locked:
            device.failed_attempts = 0
            device.locked_until = now + LOCKOUT
        device.save(update_fields=["failed_attempts", "locked_until"])
        log.info("code_invalid user=%s purpose=%s attempts=%s", user.pk, purpose, attempts)
        if locked:
            log.warning("locked user=%s purpose=%s minutes=%s",
                        user.pk, purpose, int(LOCKOUT.total_seconds() // 60))
        return INVALID


def start_setup(user):
    """Creates a fresh unconfirmed device. Returns None if 2FA is already on."""
    if user.two_factor_enabled:
        return None
    secret = pyotp.random_base32()
    TOTPDevice.objects.update_or_create(user=user, defaults={
        "secret": secret, "confirmed": False, "last_used_step": None,
        "failed_attempts": 0, "locked_until": None,
    })
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=ISSUER)
    log.info("setup_started user=%s", user.pk)
    return {
        "secret": secret,
        "otpauth_uri": uri,
        "qr_code": segno.make(uri, error="m").svg_data_uri(scale=5, border=2),
    }


def confirm_setup(user, code):
    """Enables 2FA once the new device produces a valid code. Returns (result, recovery_codes)."""
    result = check_code(user, code, allow_recovery=False, confirmed=False, purpose="enable")
    if result != OK:
        return result, None
    codes = [_new_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
    with transaction.atomic():
        TOTPDevice.objects.filter(user=user).update(confirmed=True)
        RecoveryCode.objects.filter(user=user).delete()
        RecoveryCode.objects.bulk_create(
            RecoveryCode(user=user, code_hash=_digest(_normalize_recovery(value)))
            for value in codes
        )
    log.info("enabled user=%s recovery_codes=%s", user.pk, len(codes))
    return OK, codes


def disable(user, code):
    result = check_code(user, code, purpose="disable")
    if result == OK:
        with transaction.atomic():
            TOTPDevice.objects.filter(user=user).delete()
            RecoveryCode.objects.filter(user=user).delete()
        log.info("disabled user=%s", user.pk)
    return result


def recovery_codes_remaining(user):
    return RecoveryCode.objects.filter(user=user, used_at__isnull=True).count()
