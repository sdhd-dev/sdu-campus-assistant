from django.db import migrations


def move_app_only_users_to_email_codes(apps, schema_editor):
    # Accounts protected only by the authenticator app keep two-step verification by
    # switching to email codes; their existing recovery codes still work.
    User = apps.get_model("accounts", "User")
    User.objects.filter(totp_device__confirmed=True, email_two_factor=False).update(
        email_two_factor=True,
    )


class Migration(migrations.Migration):
    """Removes the authenticator app (TOTP). Irreversible: the app secrets are deleted."""

    dependencies = [
        ("accounts", "0006_email_two_factor"),
    ]

    operations = [
        migrations.RunPython(move_app_only_users_to_email_codes, migrations.RunPython.noop),
        migrations.DeleteModel(name="TOTPDevice"),
    ]
