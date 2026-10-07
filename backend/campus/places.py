from .models import CampusPlace
from .views import block_details


def places_queryset():
    return CampusPlace.objects.select_related("block", "room__block", "recommended_entrance")


def place_data(place):
    block = place.block or (place.room.block if place.room_id else None)
    entry = place.recommended_entrance
    return {"id": place.pk, "type": "place", "code": place.slug, "name": place.name,
            "category": place.category, "description": place.description,
            "block": block_details(block) if block else None,
            "floor": place.floor if place.floor is not None else (place.room.floor if place.room_id else None),
            "room_code": place.room.code if place.room_id else None,
            "entrance": {"code": entry.code if entry else None, "name": entry.name if entry else None,
                         "description": entry.description if entry else "", "status": "UNKNOWN"},
            "opening_hours": place.opening_hours, "source": place.source,
            "verification_status": place.verification_status,
            "verified_at": place.verified_at, "provisional": place.verification_status != "VERIFIED",
            "map_available": bool(place.map_element), "map_element": place.map_element}
