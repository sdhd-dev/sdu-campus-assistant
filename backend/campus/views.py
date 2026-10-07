"""Session-protected inventory search. Numbering never creates inventory."""
import re

from django.db import DatabaseError
from django.db.models import Case, IntegerField, Q, Value, When
from django.db.models.expressions import RawSQL
from django.views.decorators.cache import never_cache
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from accounts.views import CSRFAuthentication, UNAUTHENTICATED
from .models import Block, Room
from .numbering import normalize_room_code

MAX_QUERY_LENGTH = 80
MAX_PAGE = 100
MAX_PAGE_SIZE = 50

# C-locale databases do not necessarily case-map Cyrillic with UPPER alone.
# Keep prepared Russian names searchable independently of the cluster locale.
CYRILLIC_LOWER = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
CYRILLIC_UPPER = CYRILLIC_LOWER.upper()
NORMALIZED_SQL = "translate(UPPER(btrim(regexp_replace({}, '\\s+', ' ', 'g'))), %s, %s)"


def normalized(value):
    return " ".join(value.split()).upper()


def entrance_data(entrance, block, override=False):
    # The prepared schema has no confidence field for room-specific overrides.
    # Never borrow the block's confidence for a different entrance.
    return {
        "code": entrance.code if entrance else None,
        "name": entrance.name if entrance else None,
        "description": entrance.description if entrance else "",
        "status": "UNKNOWN" if override else block.recommendation_status,
        "note": "Рекомендация для кабинета; статус пока не уточнён." if override
                else block.recommendation_note,
    }


def room_data(room):
    return {
        "id": room.pk, "type": "room", "code": room.code, "name": room.name,
        "block": {"id": room.block_id, "code": room.block.code, "name": room.block.name},
        "floor": room.floor, "kind": room.kind, "description": room.description,
        "entrance": entrance_data(room.effective_entrance, room.block,
                                  override=room.recommended_entrance_id is not None),
        "source": room.source,
        "provisional": not room.source or room.source.startswith("Сгенерировано"),
    }


def block_data(block):
    return {
        "id": block.pk, "type": "block", "code": block.code, "name": block.name,
        "block": {"id": block.pk, "code": block.code, "name": block.name},
        "description": block.recommendation_note,
        "entrance": entrance_data(block.recommended_entrance, block),
        "source": "", "provisional": True,
    }


@never_cache
@api_view(["GET"])
@authentication_classes([CSRFAuthentication])
@permission_classes([AllowAny])
def search(request):
    if not request.user.is_authenticated:
        return Response(UNAUTHENTICATED, status=401)
    raw = request.query_params.get("q", "")
    if len(raw) > MAX_QUERY_LENGTH:
        return Response({"detail": "Запрос не должен превышать 80 символов."}, status=400)
    try:
        page = int(request.query_params.get("page", "1"))
        size = int(request.query_params.get("page_size", "20"))
        if not 1 <= page <= MAX_PAGE or not 1 <= size <= MAX_PAGE_SIZE:
            raise ValueError
    except ValueError:
        return Response({"detail": "page: 1–100; page_size: 1–50."}, status=400)
    query = normalized(raw)
    empty = {"query": query, "count": 0, "page": page, "page_size": size,
             "next_page": None, "results": []}
    if not query:
        return Response(empty)
    code = normalize_room_code(re.sub(r"\s+", "", query))
    block_code = re.sub(r"^(БЛОК|BLOCK)\s+", "", query)
    # JSON aliases are compared individually, not as serialized JSON text.
    # The escaped LIKE argument keeps %, _ and backslashes literal.
    pattern = "%" + query.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_") + "%"
    is_block = block_code in Block.Code.values
    alias_sql = NORMALIZED_SQL.format("a")
    rooms = Room.objects.select_related("block", "block__recommended_entrance", "recommended_entrance").annotate(
        normalized_name=RawSQL(NORMALIZED_SQL.format("campus_room.name"), [CYRILLIC_LOWER, CYRILLIC_UPPER]),
        alias_exact=RawSQL("EXISTS (SELECT 1 FROM jsonb_array_elements_text(aliases) a WHERE "
                           + alias_sql + " = %s)", [CYRILLIC_LOWER, CYRILLIC_UPPER, query]),
        alias_partial=RawSQL("EXISTS (SELECT 1 FROM jsonb_array_elements_text(aliases) a WHERE "
                             + alias_sql + " LIKE %s)", [CYRILLIC_LOWER, CYRILLIC_UPPER, pattern]),
    )
    room_filter = Q(block__code=block_code) if is_block else (
        Q(code__icontains=code) | Q(normalized_name__contains=query) | Q(alias_partial=True))
    rooms = rooms.filter(room_filter).annotate(
        rank=Case(When(Q(code__iexact=code) | Q(alias_exact=True), then=Value(0)),
                  default=Value(1), output_field=IntegerField()),
    ).order_by("rank", "code")
    blocks = Block.objects.select_related("recommended_entrance").annotate(
        normalized_name=RawSQL(NORMALIZED_SQL.format("campus_block.name"), [CYRILLIC_LOWER, CYRILLIC_UPPER]),
    ).filter(Q(code=block_code) if is_block else Q(normalized_name__contains=query)).annotate(
        rank=Case(When(code=block_code, then=Value(0)),
                  default=Value(1), output_field=IntegerField())).order_by("rank", "code")
    try:
        count = rooms.count() + blocks.count()
        end = page * size
        # Each independently ordered source only needs its first `end` rows.
        # Sorting that bounded merge yields stable pagination across both types.
        matches = [(r.rank, r.code, "room", room_data(r)) for r in rooms[:end]]
        matches += [(b.rank, b.code, "block", block_data(b)) for b in blocks[:end]]
        matches.sort(key=lambda item: item[:3])
        return Response({**empty, "count": count,
                         "next_page": page + 1 if count > end and page < MAX_PAGE else None,
                         "results": [item[3] for item in matches[(page - 1) * size:end]]})
    except DatabaseError:
        return Response({"detail": "Поиск временно недоступен. Повторите запрос."}, status=503)
