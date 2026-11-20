from django.db import migrations


def update_sitam(apps, schema_editor):
    name = "SITAM (School of IT and Applied Mathematics)"
    database = schema_editor.connection.alias
    apps.get_model("campus", "Block").objects.using(database).filter(code__in=["F", "I"]).update(
        faculty_name=name, faculty_source="Project owner clarification, 2026-10-15")
    apps.get_model("campus", "DirectoryFaculty").objects.using(database).filter(code="SITAM").update(name=name)


class Migration(migrations.Migration):
    dependencies = [("campus", "0006_person_search_original_person_search_transliterated_and_more")]
    operations = [migrations.RunPython(update_sitam, migrations.RunPython.noop)]
