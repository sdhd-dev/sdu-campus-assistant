from datetime import date
from django.core.management.base import BaseCommand
from django.db import transaction
from campus.models import CampusPlace

PLACES = [
    dict(slug="library", name="Library", category="LIBRARY", aliases=["library", "библиотека"],
         description="The university library occupies three floors and has a separate entrance from outside.",
         location="Library area", details=["Three floors", "Separate outdoor entrance"],
         map_element="library-area", map_note="Approximate library area. Exact boundaries and outdoor entrance position are not confirmed.",
         photo="/campus/places/library.webp", photo_alt="SDU library entrance with glass doors and stairs"),
    dict(slug="red-hall", name="Red Hall", category="AUDITORIUM", aliases=["red hall", "ред холл"],
         description="A large auditorium in Block A used for university events.", location="Block A",
         map_element="block:A", map_note="Shown by Block A. The auditorium's exact position and floor are not confirmed.",
         photo="/campus/places/red-hall.webp", photo_alt="Large SDU auditorium with red seats and a red stage curtain"),
    dict(slug="mini-red-hall", name="Mini Red Hall", category="AUDITORIUM", aliases=["mini red hall", "мини ред холл"],
         description="A smaller auditorium located near Entrance G, used for university events.", location="Near Entrance G",
         map_element="near-entrance:G", map_note="Approximate area near Entrance G, between Blocks G and H. Exact auditorium position, block and floor are not confirmed.",
         photo="/campus/places/mini-red-hall.webp", photo_alt="Small SDU auditorium with yellow walls and red chairs"),
]

class Command(BaseCommand):
    help = "Add three team-confirmed facilities; repeat safely and preserve existing manual data."

    @transaction.atomic
    def handle(self, *args, **options):
        created = 0
        for values in PLACES:
            defaults = dict(values, source="Confirmed by the project team, 2026-10-08", verification_status="VERIFIED", verified_at=date(2026,10,8))
            slug = defaults.pop("slug")
            obj, new = CampusPlace.objects.get_or_create(slug=slug, defaults=defaults)
            created += int(new)
            if not new:
                changed = [k for k,v in defaults.items() if getattr(obj,k) != v]
                if changed:
                    self.stderr.write(f"Conflict: {slug} ({', '.join(changed)}); existing data preserved.")
        self.stdout.write(f"Campus places: {created} created; existing records preserved.")
