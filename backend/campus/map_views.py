"""Map selections resolve inventory, not hypothetical room coordinates."""
import re

from django.db import DatabaseError
from django.views.decorators.cache import never_cache
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from accounts.views import CSRFAuthentication, UNAUTHENTICATED
from .models import Block, Entrance, Room, CampusPlace
from .views import block_data, room_data, block_details


def barrel_for(room):
    if room.kind != Room.Kind.BARREL:
        return None
    labels = set()
    for alias in [*room.aliases, room.name]:
        match = re.fullmatch(r"(?:BARREL\s+|БОЧКА\s+)?([A-D])([12])", alias.strip().upper())
        if match:
            labels.add(match[1] + match[2])
    # Ambiguous or unknown aliases must not invent a physical map location.
    return next(iter(labels)) if len(labels) == 1 else None


def map_data(data, *, block=None, entrance=None, barrel=None, context_only=False):
    return {**data, "map": {"block_code": block, "entrance_code": entrance,
                           "barrel_code": barrel[0] if barrel else None, "barrel_label": barrel,
                           "context_only": context_only,
                           "entrance_position_provisional": entrance == "I"}}


@never_cache
@api_view(["GET"])
@authentication_classes([CSRFAuthentication])
@permission_classes([AllowAny])
def location(request):
    if not request.user.is_authenticated:
        return Response(UNAUTHENTICATED, status=401)
    kind = request.query_params.get("type", "")
    code = request.query_params.get("code", "").strip().upper()
    if kind not in {"room", "block", "entrance", "place"} or len(code) > 4:
        return Response({"detail": "Choose a room ID, block code or entrance code."}, status=400)
    try:
        if kind == "place":
            from .places import places_queryset, place_data
            raw_id = request.query_params.get("id", "")
            if not re.fullmatch(r"[0-9]{1,10}", raw_id) or int(raw_id) < 1:
                return Response({"detail": "A positive place ID is required."}, status=400)
            place = places_queryset().get(pk=int(raw_id))
            data = place_data(place)
            element = place.map_element.split(":")
            # Metadata is not a map binding. Never infer a highlight from the block.
            result = map_data(data, block=element[1] if element[0] == "block" else None,
                              barrel=element[1] if element[0] == "barrel" else None,
                              entrance=element[1] if element[0] == "entrance" else None)
            result["map"]["element"] = place.map_element
            return Response(result)
        if kind == "room":
            raw_id = request.query_params.get("id", "")
            if not re.fullmatch(r"[0-9]{1,10}", raw_id) or int(raw_id) < 1:
                return Response({"detail": "A positive room ID is required."}, status=400)
            room = Room.objects.select_related("block", "block__recommended_entrance", "recommended_entrance").get(pk=int(raw_id))
            entrance = room.effective_entrance
            return Response(map_data(room_data(room), block=room.block.code,
                                     entrance=entrance.code if entrance else None,
                                     barrel=barrel_for(room)))
        if kind == "block":
            if code in "ABC" and len(code) == 1:
                # These approved SVG context elements do not create inventory.
                return Response(map_data({"id": None, "type": "block", "code": code,
                    "name": f"Block {code}", "block": {"code": code}, "provisional": True,
                    "entrance": {"code": None, "name": None, "status": "UNKNOWN"},
                    "description": "Context building. Facility details and entrance recommendation are not confirmed."},
                    block=code, context_only=True))
            block = Block.objects.select_related("recommended_entrance").get(code=code)
            return Response(map_data(block_data(block), block=block.code,
                                     entrance=block.recommended_entrance.code if block.recommended_entrance else None))
        entry = Entrance.objects.get(code=code)
        return Response(map_data({"id": entry.pk, "type": "entrance", "code": entry.code,
                                  "name": entry.name, "description": entry.description}, entrance=entry.code))
    except (Room.DoesNotExist, Block.DoesNotExist, Entrance.DoesNotExist, CampusPlace.DoesNotExist):
        return Response({"detail": "Location not found in the campus inventory."}, status=404)
    except DatabaseError:
        return Response({"detail": "Campus locations are temporarily unavailable. Please retry."}, status=503)


@never_cache
@api_view(["GET"])
@authentication_classes([CSRFAuthentication])
@permission_classes([AllowAny])
def map_blocks(request):
    if not request.user.is_authenticated:
        return Response(UNAUTHENTICATED, status=401)
    try:
        return Response({"blocks": [block_details(block) for block in Block.objects.all()]})
    except DatabaseError:
        return Response({"detail": "Building details are temporarily unavailable. Please retry."}, status=503)
