"""Confirms a Student or Staff status with a one-time code sent to a university email."""
import logging
import math
import re
import secrets
import smtplib
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from .models import UniversityEmailChallenge, UniversityEmailSend

User = get_user_model()
log = logging.getLogger("accounts.verification")

CODE_LIFETIME = timedelta(minutes=10)
MAX_FAILURES = 5
RESEND_COOLDOWN = timedelta(seconds=60)
SEND_WINDOW = timedelta(hours=1)
MAX_SENDS_PER_ACCOUNT = 5
MAX_SENDS_PER_ADDRESS = 5

SENT, RATE_LIMITED = "sent", "rate_limited"
OK, INVALID, EXPIRED, LOCKED, TAKEN, NO_CODE, NOT_UNIVERSITY = (
    "ok", "invalid", "expired", "locked", "taken", "no_code", "not_university",
)


class MailUnavailable(Exception):
    pass


def enabled():
    return bool(settings.UNIVERSITY_STUDENT_DOMAINS or settings.UNIVERSITY_STAFF_DOMAINS)


def affiliation_for_domain(domain):
    """Maps an exact university domain to a status. Also the entry point for a future
    Google Workspace path, where the domain would come from a verified "hd" claim."""
    domain = (domain or "").lower()
    if domain in settings.UNIVERSITY_STUDENT_DOMAINS:
        return User.VerifiedAffiliation.STUDENT
    if domain in settings.UNIVERSITY_STAFF_DOMAINS:
        return User.VerifiedAffiliation.STAFF
    return None


def affiliation_for_email(email):
    return affiliation_for_domain(email.rpartition("@")[2])


def mask(email):
    """For logs: the first character and the domain only."""
    local, _, domain = email.rpartition("@")
    return f"{local[:1]}***@{domain}"


def _digest(*parts):
    # Keyed with SECRET_KEY: a 6-digit code's plain hash could be reversed by brute force.
    value = "\0".join(str(part) for part in parts)
    return salted_hmac("accounts.university_email", value, algorithm="sha256").hexdigest()


def _code_digest(user, email, code):
    return _digest("code", user.pk, email, code)


def _address_digest(email):
    return _digest("address", email)


def _retry_after(user, now, email=None):
    """Seconds until another code may be sent; 0 when it may be sent now."""
    recent = UniversityEmailSend.objects.filter(sent_at__gt=now - SEND_WINDOW)
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


def _send(email, code):
    minutes = int(CODE_LIFETIME.total_seconds() // 60)
    send_mail(
        "Your SDU Campus Assistant verification code",
        f"Your verification code is {code}.\n\n"
        f"It expires in {minutes} minutes and works once. If you didn't ask to confirm "
        "your university status in SDU Campus Assistant, you can ignore this email.\n",
        None, [email],
    )


def start(user, email):
    """Sends a code to a university address. Returns (result, retry_after_seconds).

    An address already verified for another account gets no email, but the caller sees
    exactly the same result, so this cannot be used to discover whose address it is.
    """
    now = timezone.now()
    with transaction.atomic():
        # Serialises one account's requests, so its limits cannot be raced.
        User.objects.select_for_update().only("pk").get(pk=user.pk)
        UniversityEmailSend.objects.filter(sent_at__lte=now - SEND_WINDOW).delete()
        retry = _retry_after(user, now, email)
        if retry:
            log.warning("code_rate_limited user=%s email=%s", user.pk, mask(email))
            return RATE_LIMITED, retry
        taken = User.objects.filter(university_email__iexact=email).exclude(pk=user.pk).exists()
        code = f"{secrets.randbelow(10 ** 6):06d}"
        if not taken:
            try:
                _send(email, code)
            except (smtplib.SMTPException, OSError) as error:
                # The exception text can contain the address, so only its type is logged.
                log.error("code_send_failed user=%s email=%s error=%s",
                          user.pk, mask(email), type(error).__name__)
                raise MailUnavailable from error
        UniversityEmailChallenge.objects.update_or_create(user=user, defaults={
            "email": email, "code_hash": _code_digest(user, email, code),
            "expires_at": now + CODE_LIFETIME, "failed_attempts": 0,
        })
        UniversityEmailSend.objects.create(user=user, email_digest=_address_digest(email), sent_at=now)
    if taken:
        log.info("code_withheld user=%s email=%s reason=verified_for_another_account",
                 user.pk, mask(email))
    else:
        log.info("code_sent user=%s email=%s", user.pk, mask(email))
    return SENT, 0


def confirm(user, code):
    """Checks the pending code and, if it matches, records the verified status."""
    code = code.strip() if isinstance(code, str) else ""
    now = timezone.now()
    with transaction.atomic():
        # The row lock serialises attempts, so a code cannot be used twice.
        challenge = UniversityEmailChallenge.objects.select_for_update().filter(user=user).first()
        if challenge is None:
            return NO_CODE
        email = challenge.email
        if challenge.expires_at <= now:
            challenge.delete()
            log.info("code_expired user=%s email=%s", user.pk, mask(email))
            return EXPIRED
        if not (re.fullmatch(r"\d{6}", code)
                and constant_time_compare(challenge.code_hash, _code_digest(user, email, code))):
            challenge.failed_attempts += 1
            if challenge.failed_attempts >= MAX_FAILURES:
                challenge.delete()
                log.warning("code_locked user=%s email=%s attempts=%s",
                            user.pk, mask(email), MAX_FAILURES)
                return LOCKED
            challenge.save(update_fields=["failed_attempts"])
            log.info("code_invalid user=%s email=%s attempts=%s",
                     user.pk, mask(email), challenge.failed_attempts)
            return INVALID
        challenge.delete()
        # Settings may have changed since the code was sent.
        affiliation = affiliation_for_email(email)
        if affiliation is None:
            log.info("verification_refused user=%s email=%s reason=not_university_domain",
                     user.pk, mask(email))
            return NOT_UNIVERSITY
        try:
            # The unique constraint is the final word if two accounts confirm at once.
            with transaction.atomic():
                if User.objects.filter(university_email__iexact=email).exclude(pk=user.pk).exists():
                    raise IntegrityError
                User.objects.filter(pk=user.pk).update(
                    university_email=email, verified_affiliation=affiliation,
                    affiliation_verified_at=now, affiliation_source=User.AffiliationSource.EMAIL,
                )
        except IntegrityError:
            log.warning("verification_conflict user=%s email=%s", user.pk, mask(email))
            return TAKEN
    user.refresh_from_db(fields=[
        "university_email", "verified_affiliation", "affiliation_verified_at", "affiliation_source",
    ])
    log.info("verified user=%s email=%s affiliation=%s", user.pk, mask(email), affiliation)
    return OK


def cancel(user):
    UniversityEmailChallenge.objects.filter(user=user).delete()


def remove(user):
    """Clears the verified status and frees the address for another account."""
    with transaction.atomic():
        UniversityEmailChallenge.objects.filter(user=user).delete()
        previous = user.university_email
        User.objects.filter(pk=user.pk).update(
            university_email=None, verified_affiliation=None,
            affiliation_verified_at=None, affiliation_source=None,
        )
    user.refresh_from_db(fields=[
        "university_email", "verified_affiliation", "affiliation_verified_at", "affiliation_source",
    ])
    if previous:
        log.info("verification_removed user=%s email=%s", user.pk, mask(previous))


def state(user):
    now = timezone.now()
    challenge = UniversityEmailChallenge.objects.filter(user=user, expires_at__gt=now).first()
    return {
        "verified_affiliation": user.verified_affiliation,
        "university_email": user.university_email,
        "verified_at": user.affiliation_verified_at.isoformat() if user.affiliation_verified_at else None,
        "pending_email": challenge.email if challenge else None,
        "resend_in": _retry_after(user, now),
        "student_domains": sorted(settings.UNIVERSITY_STUDENT_DOMAINS),
        "staff_domains": sorted(settings.UNIVERSITY_STAFF_DOMAINS),
    }
