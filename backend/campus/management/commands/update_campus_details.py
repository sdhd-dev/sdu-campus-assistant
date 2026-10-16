from django.core.management.base import BaseCommand

from campus.approved_details import update_approved_details


class Command(BaseCommand):
    help = 'Fill approved English barrel descriptions and faculty details without overwriting manual corrections.'

    def handle(self, *args, **options):
        update_approved_details(self.stdout, self.stderr)
        from campus.entrance_details import update_entrances
        update_entrances(self.stdout, self.stderr)
