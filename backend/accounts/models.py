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
