import json
from datetime import date
from pathlib import Path
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from campus.models import CampusPlace, Block, Entrance, Room

FIELDS = {"slug", "name", "category", "aliases", "description", "block", "floor", "room", "recommended_entrance", "map_element", "opening_hours", "source", "verification_status", "verified_at"}

class Command(BaseCommand):
    help = "Import verified campus places from version-1 JSON; atomic, dry-run, preserve differing manual data unless --update is explicitly supplied."

    def add_arguments(self, parser):
        parser.add_argument("file")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--update", action="store_true", help="Explicitly approve replacing differing fields of existing records")

    def handle(self, *args, **options):
        try:
            if Path(options["file"]).stat().st_size > 1000000:
                raise ValueError("File exceeds 1 MB")
            payload = json.loads(Path(options["file"]).read_text())
            if not isinstance(payload, dict) or set(payload) != {"version", "places"} or payload["version"] != 1 or not isinstance(payload["places"], list) or len(payload["places"]) > 500:
                raise ValueError("Expected version 1 and at most 500 places")
            seen = set()
            with transaction.atomic():
                count = 0
                for row in payload["places"]:
                    if not isinstance(row, dict) or set(row) - FIELDS or not {"slug", "name", "category", "source", "verification_status", "verified_at"} <= set(row):
                        raise ValueError("Unknown or missing fields")
                    if not isinstance(row["slug"], str) or row["slug"] in seen:
                        raise ValueError("Invalid or duplicate slug")
                    seen.add(row["slug"])
                    if row["verification_status"] != "VERIFIED":
                        raise ValueError("Only verified records can be imported")
                    values = dict(row)
                    for field, model in [("block", Block), ("room", Room), ("recommended_entrance", Entrance)]:
                        if field in values:
                            key = values[field]
                            if key is not None and not isinstance(key, str):
                                raise ValueError(f"{field} must be a code or null")
                            values[field] = model.objects.get(code=key) if key else None
                    if not isinstance(values["verified_at"], str):
                        raise ValueError("Verification date must be YYYY-MM-DD")
                    values["verified_at"] = date.fromisoformat(values["verified_at"])
                    for field in FIELDS - {"aliases", "floor", "block", "room", "recommended_entrance", "verified_at"}:
                        if field in values and not isinstance(values[field], str):
                            raise ValueError(f"{field} must be text")
                    if "floor" in values and values["floor"] is not None and (type(values["floor"]) is not int):
                        raise ValueError("Floor must be an integer or null")
                    current = CampusPlace.objects.select_for_update().filter(slug=row["slug"]).first()
                    obj = current or CampusPlace(slug=row["slug"])
                    different = current and any(getattr(current, k) != v for k, v in values.items())
                    if different and not options["update"]:
                        raise ValueError(f"Conflict for {obj.slug}; existing data preserved. Review before using --update")
                    for key, value in values.items():
                        setattr(obj, key, value)
                    obj.full_clean()
                    if not current or different:
                        obj.save()
                        count += 1
                if options["dry_run"]:
                    transaction.set_rollback(True)
                self.stdout.write(f"{'Dry run' if options['dry_run'] else 'Import'}: {count} changes; {len(seen)} records validated.")
        except (OSError, ValueError, TypeError, ValidationError, Block.DoesNotExist, Room.DoesNotExist, Entrance.DoesNotExist) as error:
            raise CommandError(str(error)) from error
