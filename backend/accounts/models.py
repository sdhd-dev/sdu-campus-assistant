from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower

from .managers import UserManager


class User(AbstractUser):
    class ProfileType(models.TextChoices):
        STUDENT = "STUDENT", "Student"
        STAFF = "STAFF", "Staff"
        VISITOR = "VISITOR", "Visitor"

    username = None
    email = models.EmailField(unique=True)
    profile_type = models.CharField(
        max_length=7, choices=ProfileType.choices, default=ProfileType.VISITOR
    )
    # Google's stable account id ("sub"), not the Google email, which can change.
    google_subject = models.CharField(max_length=255, unique=True, null=True, blank=True)

    class VerifiedAffiliation(models.TextChoices):
        STUDENT = "STUDENT", "Student"
        STAFF = "STAFF", "Staff"

    class AffiliationSource(models.TextChoices):
        EMAIL = "EMAIL", "University email code"
        # Reserved: a verified Google Workspace "hd" claim on a university domain.
        GOOGLE_WORKSPACE = "GOOGLE_WORKSPACE", "Google Workspace"

    # Proven status. profile_type may be Student or Staff only when it matches this.
    # A verified user may still choose Visitor, and return without verifying again.
    # Grants no permissions.
    verified_affiliation = models.CharField(
        max_length=7, choices=VerifiedAffiliation.choices, null=True, blank=True,
    )
    university_email = models.EmailField(max_length=254, null=True, blank=True)
    affiliation_verified_at = models.DateTimeField(null=True, blank=True)
    affiliation_source = models.CharField(
        max_length=16, choices=AffiliationSource.choices, null=True, blank=True,
    )

    # Two-step verification by a code sent to the account email.
    email_two_factor = models.BooleanField(default=False)
    # Lockout for recovery codes; email codes burn on their own.
    two_factor_failed_attempts = models.PositiveSmallIntegerField(default=0)
    two_factor_locked_until = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique"),
            models.CheckConstraint(
                condition=models.Q(profile_type__in=["STUDENT", "STAFF", "VISITOR"]),
                name="accounts_user_valid_profile_type",
            ),
            # One university address proves a status for one account only.
            models.UniqueConstraint(
                Lower("university_email"), name="accounts_user_university_email_ci_unique",
            ),
            # Either every verification field is set, or none is.
            models.CheckConstraint(
                condition=models.Q(
                    verified_affiliation__isnull=True, university_email__isnull=True,
                    affiliation_verified_at__isnull=True, affiliation_source__isnull=True,
                ) | models.Q(
                    verified_affiliation__in=["STUDENT", "STAFF"], university_email__isnull=False,
                    affiliation_verified_at__isnull=False,
                    affiliation_source__in=["EMAIL", "GOOGLE_WORKSPACE"],
                ),
                name="accounts_user_verified_affiliation_consistent",
            ),
            # Student and Staff must be proven; Visitor is always allowed.
            models.CheckConstraint(
                condition=models.Q(profile_type="VISITOR")
                # IS NOT NULL matters: a comparison with NULL would let the check pass.
                | models.Q(verified_affiliation__isnull=False, profile_type=models.F("verified_affiliation")),
                name="accounts_user_role_requires_verification",
            ),
        ]

    def __str__(self):
        return self.email

    @property
    def google_linked(self):
        return bool(self.google_subject)

    @property
    def two_factor_enabled(self):
        return self.email_two_factor


class RecoveryCode(models.Model):
    """A single-use fallback when an email code can't be received. Issued when two-step
    verification is turned on. Only a SHA-256 digest is stored."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recovery_codes")
    code_hash = models.CharField(max_length=64)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "code_hash"], name="accounts_recovery_code_unique"),
        ]


class EmailCode(models.Model):
    """A user's pending one-time email code for one purpose. Only a keyed digest is stored."""

    class Purpose(models.TextChoices):
        ROLE = "role", "Role verification"
        SIGN_IN = "sign_in", "Sign-in second step"
        SECURITY = "security", "Two-step verification change"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="email_codes")
    purpose = models.CharField(max_length=16, choices=Purpose.choices)
    email = models.EmailField(max_length=254)
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    failed_attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "purpose"], name="accounts_email_code_one_per_purpose"),
        ]


class EmailCodeSend(models.Model):
    """One code request, kept for an hour to rate-limit per account and per address."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    purpose = models.CharField(max_length=16, choices=EmailCode.Purpose.choices)
    # A keyed digest, so the table does not collect addresses.
    email_digest = models.CharField(max_length=64, db_index=True)
    sent_at = models.DateTimeField(db_index=True)
