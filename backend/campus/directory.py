"""Shared directory serialization for search and room/map cards."""
from django.db.models import Case, IntegerField, Prefetch, Q, Value, When

from .models import OfficeAssignment, Person
from .name_search import latin_search_key, normalize_name


def visible_people():
    return Person.objects.exclude(verification_status=Person.Verification.REVIEW)


def room_office_prefetch():
    return Prefetch("office_assignments", queryset=OfficeAssignment.objects.exclude(
        person__verification_status=Person.Verification.REVIEW
    ).select_related("person", "faculty").order_by("person__search_name", "pk"))


def office_data(office):
    room = office.room
    return {
        "id": office.pk, "source_room": office.source_room, "door": office.door,
        "alternative_label": office.alternative_label,
        "faculty": {"code": office.faculty.code, "name": office.faculty.name},
        "room": {"id": room.pk, "code": room.code, "block": room.block.code, "floor": room.floor} if room else None,
        "map_available": bool(room and room.block.code in "ABCDEFGHI"),
        "note": office.note,
    }


def person_data(person):
    offices = [office_data(o) for o in person.offices.all()]
    return {
        "id": person.pk, "type": "person", "name": person.full_name,
        "title": person.title, "source_name": person.source_name, "role": person.role,
        "verification_status": person.verification_status, "source": person.source,
        "source_image": person.source_image, "offices": offices,
        "map_available": any(o["map_available"] for o in offices),
    }


def matching_people(query, faculty=""):
    normalized = normalize_name(query)
    variants = Q(search_name__contains=normalized) | Q(search_original__contains=normalized)
    key = latin_search_key(query)
    if key:
        variants |= Q(search_transliterated__contains=key)
    people = visible_people().filter(variants)
    if faculty:
        people = people.filter(offices__faculty__code=faculty).distinct()
    return people.annotate(rank=Case(When(Q(search_name=normalized) | Q(search_original=normalized), then=Value(0)),
        default=Value(1), output_field=IntegerField())).order_by("rank", "search_name", "pk").prefetch_related(
            Prefetch("offices", queryset=OfficeAssignment.objects.select_related("faculty", "room__block").order_by("source_room", "pk")))


def room_people(room):
    cache = getattr(room, "_prefetched_objects_cache", {})
    assignments = cache.get("office_assignments")
    if assignments is None:
        assignments = room.office_assignments.exclude(
            person__verification_status=Person.Verification.REVIEW
        ).select_related("person", "faculty").order_by("person__search_name", "pk")
    return [{"id": o.person_id, "name": o.person.full_name, "title": o.person.title,
             "faculty": {"code": o.faculty.code, "name": o.faculty.name},
             "source_room": o.source_room, "door": o.door, "alternative_label": o.alternative_label,
             "verification_status": o.person.verification_status} for o in assignments if o.person.verification_status != Person.Verification.REVIEW]
