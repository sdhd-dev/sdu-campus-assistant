"""One-time 6-digit codes sent by email, shared by every flow that needs one.

A code lives 10 minutes, works once, and is stored only as an HMAC keyed with
SECRET_KEY. Five wrong attempts burn it. Sends are limited per account and per
address. Log lines carry the user id, purpose, and a masked address only.
"""
import logging
import math
import re
import secrets
import smtplib
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from .models import EmailCode, EmailCodeSend

User = get_user_model()

CODE_LIFETIME = timedelta(minutes=10)
MAX_FAILURES = 5
RESEND_COOLDOWN = timedelta(seconds=60)
SEND_WINDOW = timedelta(hours=1)
MAX_SENDS_PER_ACCOUNT = 5
MAX_SENDS_PER_ADDRESS = 5

ROLE, SIGN_IN, SECURITY = EmailCode.Purpose.ROLE, EmailCode.Purpose.SIGN_IN, EmailCode.Purpose.SECURITY
SENT, RATE_LIMITED = "sent", "rate_limited"
OK, INVALID, EXPIRED, LOCKED, NO_CODE = "ok", "invalid", "expired", "locked", "no_code"

LOGGERS = {
    ROLE: logging.getLogger("accounts.verification"),
    SIGN_IN: logging.getLogger("accounts.two_factor"),
    SECURITY: logging.getLogger("accounts.two_factor"),
}
MESSAGES = {
    ROLE: ("Your SDU Campus Assistant verification code",
           "confirm your university role"),
    SIGN_IN: ("Your SDU Campus Assistant sign-in code",
              "finish signing in"),
    SECURITY: ("Confirm a security change in SDU Campus Assistant",
               "confirm a change to your two-step verification"),
}


class MailUnavailable(Exception):
    pass


def mask(email):
    """For logs and hints: the first character and the domain only."""
    local, _, domain = email.rpartition("@")
    return f"{local[:1]}***@{domain}"


def _digest(*parts):
    # Keyed with SECRET_KEY: a 6-digit code's plain hash could be reversed by brute force.
    value = "\0".join(str(part) for part in parts)
    return salted_hmac("accounts.email_codes", value, algorithm="sha256").hexdigest()


def _code_digest(user, purpose, email, code):
    return _digest("code", purpose, user.pk, email, code)


def _address_digest(email):
    return _digest("address", email)


def retry_after(user, purpose, now=None, email=None):
    """Seconds until another code may be sent; 0 when it may be sent now."""
    now = now or timezone.now()
    recent = EmailCodeSend.objects.filter(purpose=purpose, sent_at__gt=now - SEND_WINDOW)
    mine = list(recent.filter(user=user).order_by("sent_at").values_list("sent_at", flat=True))
    waits = []
    if mine:
        waits.append(mine[-1] + RESEND_COOLDOWN - now)
    if len(mine) >= MAX_SENDS_PER_ACCOUNT:
        waits.append(mine[-MAX_SENDS_PER_ACCOUNT] + SEND_WINDOW - now)
    if email is not None:
        theirs = list(recent.filter(email_digest=_address_digest(email))
                      .order_by("sent_at").values_list("sent_at", flat=True))
        if len(theirs) >= MAX_SENDS_PER_ADDRESS:
            waits.append(theirs[-MAX_SENDS_PER_ADDRESS] + SEND_WINDOW - now)
    return max([0, *(math.ceil(wait.total_seconds()) for wait in waits)])


def _send(purpose, email, code):
    subject, action = MESSAGES[purpose]
    minutes = int(CODE_LIFETIME.total_seconds() // 60)
    send_mail(
        subject,
        f"Your code is {code}.\n\n"
        f"Use it to {action}. It expires in {minutes} minutes and works once. If you "
        "didn't request it, you can ignore this email.\n",
        None, [email],
    )


def issue(user, purpose, email, *, deliver=True, reason=None):
    """Replaces the user's pending code for this purpose. Returns (result, retry_after).

    With deliver=False the code is recorded but never sent, so the caller can answer
    exactly as if it had been.
    """
    log = LOGGERS[purpose]
    now = timezone.now()
    with transaction.atomic():
        # Serialises one account's requests, so its limits cannot be raced.
        User.objects.select_for_update().only("pk").get(pk=user.pk)
        EmailCodeSend.objects.filter(sent_at__lte=now - SEND_WINDOW).delete()
        retry = retry_after(user, purpose, now, email)
        if retry:
            log.warning("code_rate_limited user=%s purpose=%s email=%s", user.pk, purpose, mask(email))
            return RATE_LIMITED, retry
        code = f"{secrets.randbelow(10 ** 6):06d}"
        if deliver:
            try:
                _send(purpose, email, code)
            except (smtplib.SMTPException, OSError) as error:
                # The exception text can contain the address, so only its type is logged.
                log.error("code_send_failed user=%s purpose=%s email=%s error=%s",
                          user.pk, purpose, mask(email), type(error).__name__)
                raise MailUnavailable from error
        EmailCode.objects.update_or_create(user=user, purpose=purpose, defaults={
            "email": email, "code_hash": _code_digest(user, purpose, email, code),
            "expires_at": now + CODE_LIFETIME, "failed_attempts": 0,
        })
        EmailCodeSend.objects.create(
            user=user, purpose=purpose, email_digest=_address_digest(email), sent_at=now,
        )
    if deliver:
        log.info("code_sent user=%s purpose=%s email=%s", user.pk, purpose, mask(email))
    else:
        log.info("code_withheld user=%s purpose=%s email=%s reason=%s",
                 user.pk, purpose, mask(email), reason)
    return SENT, 0


def check(user, purpose, code):
    """Checks and, on success, consumes the pending code. Returns (result, email).

    Must run inside the caller's transaction when the caller writes on success,
    so the code and the change it authorises commit together.
    """
    log = LOGGERS[purpose]
    code = code.strip() if isinstance(code, str) else ""
    now = timezone.now()
    with transaction.atomic():
        # The row lock serialises attempts, so a code cannot be used twice.
        pending = EmailCode.objects.select_for_update().filter(user=user, purpose=purpose).first()
        if pending is None:
            return NO_CODE, None
        email = pending.email
        if pending.expires_at <= now:
            pending.delete()
            log.info("code_expired user=%s purpose=%s email=%s", user.pk, purpose, mask(email))
            return EXPIRED, email
        if not (re.fullmatch(r"\d{6}", code)
                and constant_time_compare(pending.code_hash, _code_digest(user, purpose, email, code))):
            pending.failed_attempts += 1
            if pending.failed_attempts >= MAX_FAILURES:
                pending.delete()
                log.warning("code_locked user=%s purpose=%s email=%s attempts=%s",
                            user.pk, purpose, mask(email), MAX_FAILURES)
                return LOCKED, email
            pending.save(update_fields=["failed_attempts"])
            log.info("code_invalid user=%s purpose=%s email=%s attempts=%s",
                     user.pk, purpose, mask(email), pending.failed_attempts)
            return INVALID, email
        pending.delete()
    return OK, email


def pending_email(user, purpose):
    code = EmailCode.objects.filter(user=user, purpose=purpose, expires_at__gt=timezone.now()).first()
    return code.email if code else None


def discard(user, purpose):
    EmailCode.objects.filter(user=user, purpose=purpose).delete()
