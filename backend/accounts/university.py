"""Confirms a Student or Staff status with a one-time code sent to a university email."""
import logging
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from . import email_codes
from .email_codes import mask

User = get_user_model()
log = logging.getLogger("accounts.verification")

SENT, RATE_LIMITED = email_codes.SENT, email_codes.RATE_LIMITED
OK, INVALID, EXPIRED, LOCKED, NO_CODE = (
    email_codes.OK, email_codes.INVALID, email_codes.EXPIRED, email_codes.LOCKED, email_codes.NO_CODE,
)
TAKEN, NOT_UNIVERSITY = "taken", "not_university"
MailUnavailable = email_codes.MailUnavailable
VERIFICATION_FIELDS = [
    "university_email", "verified_affiliation", "affiliation_verified_at", "affiliation_source",
]


def enabled():
    return bool(settings.UNIVERSITY_STUDENT_DOMAINS or settings.UNIVERSITY_STAFF_DOMAINS)


# SDU uses one domain for everyone, so the part before "@" tells the roles apart.
LOCAL_PARTS = {
    User.VerifiedAffiliation.STUDENT: re.compile(r"[0-9]+"),  # student ID
    User.VerifiedAffiliation.STAFF: re.compile(r"[a-z]+\.[a-z]+"),  # name.surname
}


def role_domains(role):
    if role == User.VerifiedAffiliation.STUDENT:
        return settings.UNIVERSITY_STUDENT_DOMAINS
    return settings.UNIVERSITY_STAFF_DOMAINS


def affiliation_for_domain(domain):
    """Maps an exact university domain to a status, or None when the domain is shared by
    both roles. Also the entry point for a future Google Workspace path, where the domain
    would come from a verified "hd" claim."""
    domain = (domain or "").lower()
    roles = [role for role in LOCAL_PARTS if domain in role_domains(role)]
    return roles[0] if len(roles) == 1 else None


def affiliation_for_email(email):
    """The role an address proves: its domain must be one of the role's domains and the
    part before "@" must match the role's format. The formats never overlap."""
    local, _, domain = email.lower().rpartition("@")
    return next((
        role for role, local_part in LOCAL_PARTS.items()
        if domain in role_domains(role) and local_part.fullmatch(local)
    ), None)


def start(user, email):
    """Sends a code to a university address whose domain the caller has matched to the
    requested role. Returns (result, retry_after_seconds).

    An address already verified for another account gets no email, but the caller sees
    exactly the same result, so this cannot be used to discover whose address it is.
    """
    taken = User.objects.filter(university_email__iexact=email).exclude(pk=user.pk).exists()
    return email_codes.issue(
        user, email_codes.ROLE, email, deliver=not taken, reason="verified_for_another_account",
    )


def confirm(user, code):
    """Checks the pending code and, if it matches, records the verified status and makes it
    the user's role."""
    now = timezone.now()
    with transaction.atomic():
        result, email = email_codes.check(user, email_codes.ROLE, code)
        if result != OK:
            return result
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
                # The verified role becomes the chosen role in the same write.
                User.objects.filter(pk=user.pk).update(
                    university_email=email, verified_affiliation=affiliation,
                    affiliation_verified_at=now, affiliation_source=User.AffiliationSource.EMAIL,
                    profile_type=affiliation,
                )
        except IntegrityError:
            log.warning("verification_conflict user=%s email=%s", user.pk, mask(email))
            return TAKEN
    user.refresh_from_db(fields=[*VERIFICATION_FIELDS, "profile_type"])
    log.info("verified user=%s email=%s affiliation=%s", user.pk, mask(email), affiliation)
    return OK


def cancel(user):
    email_codes.discard(user, email_codes.ROLE)


def remove(user):
    """Clears the verified status, returns the role to Visitor, and frees the address."""
    with transaction.atomic():
        email_codes.discard(user, email_codes.ROLE)
        previous = user.university_email
        User.objects.filter(pk=user.pk).update(
            **dict.fromkeys(VERIFICATION_FIELDS), profile_type=User.ProfileType.VISITOR,
        )
    user.refresh_from_db(fields=[*VERIFICATION_FIELDS, "profile_type"])
    if previous:
        log.info("verification_removed user=%s email=%s", user.pk, mask(previous))


def state(user):
    return {
        "profile_type": user.profile_type,
        "verified_affiliation": user.verified_affiliation,
        "university_email": user.university_email,
        "verified_at": user.affiliation_verified_at.isoformat() if user.affiliation_verified_at else None,
        "pending_email": email_codes.pending_email(user, email_codes.ROLE),
        "resend_in": email_codes.retry_after(user, email_codes.ROLE),
        "student_domains": sorted(settings.UNIVERSITY_STUDENT_DOMAINS),
        "staff_domains": sorted(settings.UNIVERSITY_STAFF_DOMAINS),
    }
