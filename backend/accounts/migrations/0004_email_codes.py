import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def clear_pending(apps, schema_editor):
    # Pending codes were hashed with the old scheme; they expire within 10 minutes anyway.
    apps.get_model("accounts", "EmailCode").objects.all().delete()


class Migration(migrations.Migration):
    """Generalises the US-06 university email tables into shared email code tables."""

    dependencies = [
        ("accounts", "0003_university_email_verification"),
    ]

    operations = [
        migrations.RenameModel("UniversityEmailChallenge", "EmailCode"),
        migrations.RenameModel("UniversityEmailSend", "EmailCodeSend"),
        migrations.RunPython(clear_pending, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="emailcode",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, related_name="email_codes",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="emailcode",
            name="purpose",
            field=models.CharField(
                choices=[("role", "Role verification"), ("sign_in", "Sign-in second step"),
                         ("security", "Two-step verification change")],
                default="role", max_length=16,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="emailcodesend",
            name="purpose",
            field=models.CharField(
                choices=[("role", "Role verification"), ("sign_in", "Sign-in second step"),
                         ("security", "Two-step verification change")],
                default="role", max_length=16,
            ),
            preserve_default=False,
        ),
        migrations.AddConstraint(
            model_name="emailcode",
            constraint=models.UniqueConstraint(
                fields=("user", "purpose"), name="accounts_email_code_one_per_purpose",
            ),
        ),
    ]
