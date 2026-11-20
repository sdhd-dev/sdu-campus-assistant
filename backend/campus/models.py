from django.core.exceptions import ValidationError
from django.db import models

from .numbering import normalize_room_code, parse_room_code


class DirectoryFaculty(models.Model):
    code = models.SlugField(unique=True)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class Person(models.Model):
    class Verification(models.TextChoices):
        LISTED = "LISTED", "Listed in source; current office unverified"
        REVIEW = "REVIEW", "Requires transcription review"
        VERIFIED = "VERIFIED", "Verified"

    source_key = models.CharField(max_length=160, unique=True)
    full_name = models.CharField(max_length=200)
    source_name = models.CharField(max_length=200)
    title = models.CharField(max_length=30, blank=True)
    search_name = models.CharField(max_length=250, editable=False, db_index=True)
    search_original = models.CharField(max_length=250, editable=False, blank=True)
    search_transliterated = models.CharField(max_length=250, editable=False, blank=True)
    role = models.CharField(max_length=20, default="TEACHER", choices=[
        ("UNKNOWN", "Role not confirmed"), ("STAFF", "Staff"), ("TEACHER", "Teacher")])
    verification_status = models.CharField(max_length=10, choices=Verification.choices, default=Verification.LISTED)
    source_image = models.CharField(max_length=200, blank=True)
    source = models.CharField(max_length=250)
    note = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        from .name_search import latin_name, latin_search_key, normalize_name
        self.full_name = latin_name(self.full_name)
        self.search_name = normalize_name(self.full_name)
        self.search_original = normalize_name(self.source_name.removeprefix("Dr "))
        self.search_transliterated = latin_search_key(self.full_name)
        # Ensure partial admin/model saves cannot leave the search index stale.
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"full_name", "search_name", "search_original", "search_transliterated"}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name


class OfficeAssignment(models.Model):
    source_key = models.CharField(max_length=180, unique=True)
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="offices")
    faculty = models.ForeignKey(DirectoryFaculty, on_delete=models.PROTECT)
    room = models.ForeignKey("Room", null=True, blank=True, on_delete=models.SET_NULL, related_name="office_assignments")
    source_room = models.CharField(max_length=40)
    door = models.CharField(max_length=10, blank=True, choices=[("RIGHT", "Right door"), ("CENTRAL", "Central door"), ("LEFT", "Left door"), ("HALL", "Hall")])
    alternative_label = models.CharField(max_length=60, blank=True)
    note = models.TextField(blank=True)

    def __str__(self):
        return f"{self.person} — {self.source_room}"


class Entrance(models.Model):
    class Code(models.TextChoices):
        MAIN = "MAIN", "Main entrance"
        G = "G", "Block G entrance"
        I = "I", "Block I entrance"

    code = models.CharField(max_length=4, choices=Code.choices, unique=True)
    name = models.CharField(max_length=120)
    block = models.ForeignKey("Block", null=True, blank=True, on_delete=models.PROTECT,
                              related_name="entrances")
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Block(models.Model):
    class Code(models.TextChoices):
        D = "D", "D"
        E = "E", "E"
        F = "F", "F"
        G = "G", "G"
        H = "H", "H"
        I = "I", "I"

    class RecommendationStatus(models.TextChoices):
        USER_REPORTED = "USER_REPORTED", "Reported by the project team"
        PROVISIONAL = "PROVISIONAL", "Assumed from the block layout; needs checking"
        UNKNOWN = "UNKNOWN", "Not established"

    code = models.CharField(max_length=1, choices=Code.choices, unique=True)
    name = models.CharField(max_length=120)
    faculty_name = models.CharField(max_length=200, blank=True)
    faculty_source = models.CharField(max_length=200, blank=True)
    horizontal_order = models.PositiveSmallIntegerField(unique=True)
    recommended_entrance = models.ForeignKey(Entrance, null=True, blank=True,
                                             on_delete=models.SET_NULL,
                                             related_name="recommended_for_blocks")
    recommendation_status = models.CharField(max_length=16,
        choices=RecommendationStatus.choices, default=RecommendationStatus.UNKNOWN)
    recommendation_note = models.TextField(blank=True)

    class Meta:
        ordering = ["horizontal_order"]
        constraints = [models.CheckConstraint(condition=models.Q(code__in=list("DEFGHI")),
                                               name="campus_block_valid_code")]

    def __str__(self):
        return self.name


class Room(models.Model):
    class Kind(models.TextChoices):
        UNKNOWN = "UNKNOWN", "Not classified"
        CLASSROOM = "CLASSROOM", "Classroom"
        STAFF_OFFICE = "STAFF_OFFICE", "Staff office"
        BARREL = "BARREL", "Barrel lecture hall"

    code = models.CharField(max_length=4, unique=True)
    block = models.ForeignKey(Block, on_delete=models.PROTECT, related_name="rooms")
    floor = models.PositiveSmallIntegerField(help_text="0 = basement; 1–4 = floors.")
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.UNKNOWN)
    name = models.CharField(max_length=120, blank=True)
    aliases = models.JSONField(default=list, blank=True)
    description = models.TextField(blank=True)
    recommended_entrance = models.ForeignKey(Entrance, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="recommended_for_rooms",
        help_text="Optional room-specific override of the block recommendation.")
    source = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["block__horizontal_order", "floor", "code"]
        indexes = [models.Index(fields=["block", "floor"], name="campus_room_block_floor")]
        constraints = [models.CheckConstraint(condition=models.Q(floor__gte=0, floor__lte=4),
                                               name="campus_room_valid_floor")]

    def clean(self):
        super().clean()
        try:
            self.code, block_code, floor = parse_room_code(self.code)
        except ValueError as error:
            raise ValidationError({"code": str(error)}) from error
        if self.block_id and self.block.code != block_code:
            raise ValidationError({"block": "Block must match the room code."})
        if self.floor != floor:
            raise ValidationError({"floor": "Floor must match the room code (0 = basement)."})
        if not isinstance(self.aliases, list) or any(not isinstance(a, str) for a in self.aliases):
            raise ValidationError({"aliases": "Aliases must be a list of strings."})

    def save(self, *args, **kwargs):
        self.code = normalize_room_code(self.code)
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def effective_entrance(self):
        return self.recommended_entrance or self.block.recommended_entrance

    def __str__(self):
        return self.code


class CampusPlace(models.Model):
    class Category(models.TextChoices):
        LIBRARY = "LIBRARY", "Library"
        OFFICE = "OFFICE", "Office"
        HALL = "HALL", "Hall"
        AUDITORIUM = "AUDITORIUM", "Auditorium"
        FOOD = "FOOD", "Food"
        OTHER = "OTHER", "Other"

    class Verification(models.TextChoices):
        UNVERIFIED = "UNVERIFIED", "Unverified"
        VERIFIED = "VERIFIED", "Verified"

    slug = models.SlugField(max_length=80, unique=True, help_text="Stable identifier; keep unchanged after publication.")
    name = models.CharField(max_length=160)
    category = models.CharField(max_length=16, choices=Category.choices)
    aliases = models.JSONField(default=list, blank=True)
    description = models.TextField(blank=True, help_text="English description")
    block = models.ForeignKey(Block, null=True, blank=True, on_delete=models.PROTECT)
    floor = models.PositiveSmallIntegerField(null=True, blank=True, help_text="0 = basement; leave blank if unknown")
    room = models.ForeignKey(Room, null=True, blank=True, on_delete=models.PROTECT)
    recommended_entrance = models.ForeignKey(Entrance, null=True, blank=True, on_delete=models.PROTECT)
    map_element = models.CharField(max_length=24, blank=True, help_text="Existing SVG element only: block:A–I, barrel:A–D, entrance:MAIN/G/I, canteen")
    location = models.CharField(max_length=160, blank=True)
    details = models.JSONField(default=list, blank=True)
    photo = models.CharField(max_length=200, blank=True, help_text="Project asset path under /campus/places/")
    photo_alt = models.CharField(max_length=200, blank=True)
    map_note = models.CharField(max_length=300, blank=True)
    opening_hours = models.CharField(max_length=300, blank=True)
    is_service = models.BooleanField(default=False)
    working_days = models.CharField(max_length=160, blank=True)
    lunch_break = models.CharField(max_length=100, blank=True)
    document_collection_hours = models.CharField(max_length=100, blank=True)
    schedule_note = models.TextField(blank=True)
    weekly_hours = models.JSONField(default=dict, blank=True)
    schedule_sources = models.JSONField(default=dict, blank=True)
    contacts = models.JSONField(default=list, blank=True)
    service_staff = models.JSONField(default=list, blank=True)
    extra_photos = models.JSONField(default=list, blank=True)
    source = models.CharField(max_length=200, blank=True)
    verification_status = models.CharField(max_length=16, choices=Verification.choices, default=Verification.UNVERIFIED)
    verified_at = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["slug"]
        constraints = [models.CheckConstraint(condition=models.Q(floor__isnull=True) | models.Q(floor__gte=0, floor__lte=4), name="campus_place_valid_floor")]

    def clean(self):
        super().clean()
        if not isinstance(self.aliases, list) or any(not isinstance(a, str) or not a.strip() or len(a) > 160 for a in self.aliases):
            raise ValidationError({"aliases": "Use a list of non-empty strings up to 160 characters."})
        if not isinstance(self.details, list) or any(not isinstance(d, str) or len(d) > 160 for d in self.details):
            raise ValidationError({"details": "Use a list of short English strings."})
        import re
        if not isinstance(self.weekly_hours, dict) or any(
            day not in {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}
            or not isinstance(hours, dict)
            or not (hours == {"closed": True} or (
                set(hours) == {"opens", "closes"}
                and all(isinstance(t, str) and re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", t) for t in hours.values())
                and hours["opens"] < hours["closes"]))
            for day, hours in (self.weekly_hours.items() if isinstance(self.weekly_hours, dict) else [])
        ):
            raise ValidationError({"weekly_hours": "Use known weekdays with opens/closes times or closed=true; omit unknown days."})
        if not isinstance(self.schedule_sources, dict) or any(not isinstance(v, str) for v in self.schedule_sources.values()):
            raise ValidationError({"schedule_sources": "Use named schedule fields and source descriptions."})
        for field, required in [("contacts", {"label", "value"}), ("service_staff", {"name", "role"}), ("extra_photos", {"path", "alt"})]:
            entries = getattr(self, field)
            if not isinstance(entries, list) or len(entries) > 30 or any(
                not isinstance(entry, dict) or set(entry) != required
                or any(not isinstance(v, str) or not v.strip() or len(v) > 300 for v in entry.values())
                for entry in entries
            ):
                raise ValidationError({field: "Use a list of labeled non-empty text entries."})
        for photo in self.extra_photos:
            if not re.fullmatch(r"/campus/places/[a-z0-9-]+\.(webp|jpg|png)", photo["path"]):
                raise ValidationError({"extra_photos": "Use permanent project photo paths and English alt text."})
        if self.photo and (not re.fullmatch(r"/campus/places/[a-z0-9-]+\.(webp|jpg|png)", self.photo) or not self.photo_alt):
            raise ValidationError({"photo": "Use a project photo path with English alt text."})
        allowed = {"", "canteen", "library-area", "near-entrance:G", *[f"block:{c}" for c in "ABCDEFGHI"], *[f"barrel:{c}" for c in "ABCD"], *[f"entrance:{c}" for c in ("MAIN", "G", "I")]}
        if self.map_element not in allowed:
            raise ValidationError({"map_element": "Choose an existing map element."})
        if self.floor is not None and not 0 <= self.floor <= 4:
            raise ValidationError({"floor": "Use 0–4 or leave unknown."})
        if self.room_id and ((self.block_id and self.block_id != self.room.block_id) or (self.floor is not None and self.floor != self.room.floor)):
            raise ValidationError("Block and floor must agree with the linked room.")
        effective_block = self.block or (self.room.block if self.room_id else None)
        if self.map_element.startswith("block:") and effective_block and self.map_element != f"block:{effective_block.code}":
            raise ValidationError({"map_element": "Map block must agree with the recorded block."})
        if self.verification_status == self.Verification.VERIFIED and (not self.source.strip() or not self.verified_at):
            raise ValidationError("Verified places require a source and verification date.")
        if self.verification_status != self.Verification.VERIFIED and self.verified_at:
            raise ValidationError({"verified_at": "Only verified records have a verification date."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name
