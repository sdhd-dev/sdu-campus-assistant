from django.core.exceptions import ValidationError
from django.db import models

from .numbering import normalize_room_code, parse_room_code


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
