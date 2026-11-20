from django.db import migrations


def update_hours(apps, schema_editor):
    Place = apps.get_model("campus", "CampusPlace")
    for place in Place.objects.using(schema_editor.connection.alias).filter(is_service=True):
        place.opening_hours = "09:00–18:00"
        place.working_days = "Monday–Friday"
        place.weekly_hours = {**(place.weekly_hours or {}),
            **{d: {"opens": "09:00", "closes": "18:00"} for d in ("MON", "TUE", "WED", "THU", "FRI")}}
        place.schedule_sources = {**(place.schedule_sources or {}),
            "opening_hours": "Project owner clarification, 2026-10-15",
            "working_days": "Project owner clarification, 2026-10-15"}
        if place.slug == "medical-center":
            place.schedule_note = "Weekday hours supplied by the project owner; Saturday and Sunday follow the published weekend schedule."
        place.save(using=schema_editor.connection.alias, update_fields=[
            "opening_hours", "working_days", "weekly_hours", "schedule_sources", "schedule_note"])


class Migration(migrations.Migration):
    dependencies = [("campus", "0008_campusplace_contacts_and_more")]
    operations = [migrations.RunPython(update_hours, migrations.RunPython.noop)]
