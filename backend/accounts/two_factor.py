"""Optional TOTP two-factor authentication with single-use recovery codes."""
import hashlib
import hmac
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


def check_code(user, code, *, allow_recovery=True, confirmed=True):
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
            return LOCKED
        if _matches_totp(device, code, now) or (allow_recovery and _matches_recovery(user, code, now)):
            device.failed_attempts = 0
            device.locked_until = None
            device.save(update_fields=["last_used_step", "failed_attempts", "locked_until"])
            return OK
        device.failed_attempts += 1
        if device.failed_attempts >= MAX_FAILURES:
            device.failed_attempts = 0
            device.locked_until = now + LOCKOUT
        device.save(update_fields=["failed_attempts", "locked_until"])
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
    return {
        "secret": secret,
        "otpauth_uri": uri,
        "qr_code": segno.make(uri, error="m").svg_data_uri(scale=5, border=2),
    }


def confirm_setup(user, code):
    """Enables 2FA once the new device produces a valid code. Returns (result, recovery_codes)."""
    result = check_code(user, code, allow_recovery=False, confirmed=False)
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
    return OK, codes


def disable(user, code):
    result = check_code(user, code)
    if result == OK:
        with transaction.atomic():
            TOTPDevice.objects.filter(user=user).delete()
            RecoveryCode.objects.filter(user=user).delete()
    return result


def recovery_codes_remaining(user):
    return RecoveryCode.objects.filter(user=user, used_at__isnull=True).count()
