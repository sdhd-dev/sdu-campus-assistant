from django.db import migrations


def add_emails(apps, schema_editor):
    Place = apps.get_model("campus", "CampusPlace")
    for slug, email in {
        "student-service-center": "ssc@sdu.edu.kz", "advising-desk": "ssc@sdu.edu.kz",
        "international-relations": "iro@sdu.edu.kz", "medical-center": "medpunkt@sdu.edu.kz",
    }.items():
        place = Place.objects.using(schema_editor.connection.alias).filter(slug=slug, is_service=True).first()
        if place is None:
            continue
        contacts = list(place.contacts or [])
        if not any(c.get("value", "").casefold() == email for c in contacts):
            contacts.append({"label": "Email", "value": email})
            place.contacts = contacts
            place.save(using=schema_editor.connection.alias, update_fields=["contacts"])


class Migration(migrations.Migration):
    dependencies = [("campus", "0009_service_weekday_hours")]
    operations = [migrations.RunPython(add_emails, migrations.RunPython.noop)]
