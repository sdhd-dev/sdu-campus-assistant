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
        ]

    def __str__(self):
        return self.email

    @property
    def google_linked(self):
        return bool(self.google_subject)

    @property
    def two_factor_enabled(self):
        device = getattr(self, "totp_device", None)
        return bool(device and device.confirmed)


class TOTPDevice(models.Model):
    """An authenticator app. Unconfirmed until the user proves it with one code."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="totp_device")
    secret = models.CharField(max_length=64)
    confirmed = models.BooleanField(default=False)
    # The last accepted 30-second step; a code is never accepted twice.
    last_used_step = models.BigIntegerField(null=True, blank=True)
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class RecoveryCode(models.Model):
    """A single-use fallback for a lost authenticator. Only a SHA-256 digest is stored."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recovery_codes")
    code_hash = models.CharField(max_length=64)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "code_hash"], name="accounts_recovery_code_unique"),
        ]
