from django.db import migrations, models
from django.db.models import F


def reset_unverified_roles(apps, schema_editor):
    # Before US-07, Student and Staff were self-selected. Unproven ones become Visitor;
    # the previous choice is not kept, so this cannot be reversed.
    User = apps.get_model("accounts", "User")
    User.objects.filter(profile_type__in=["STUDENT", "STAFF"]).exclude(
        profile_type=F("verified_affiliation"),
    ).update(profile_type="VISITOR")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_email_codes"),
    ]

    operations = [
        migrations.RunPython(reset_unverified_roles, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=models.Q(profile_type="VISITOR")
                # IS NOT NULL matters: a comparison with NULL would let the check pass.
                | models.Q(verified_affiliation__isnull=False, profile_type=models.F("verified_affiliation")),
                name="accounts_user_role_requires_verification",
            ),
        ),
    ]
