from django.db import DatabaseError
from django.views.decorators.cache import never_cache
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from accounts.views import CSRFAuthentication, UNAUTHENTICATED
from .models import Block, Room
from .views import block_data, room_data
from .map_views import barrel_for

@never_cache
@api_view(["GET"])
@authentication_classes([CSRFAuthentication])
@permission_classes([AllowAny])
def catalog(request):
    if not request.user.is_authenticated:
        return Response(UNAUTHENTICATED, status=401)
    try:
        barrels = [dict(room_data(r), barrel_label=barrel_for(r)) for r in Room.objects.filter(kind="BARREL").select_related("block", "block__recommended_entrance", "recommended_entrance") if barrel_for(r)]
        blocks = [block_data(b) for b in Block.objects.filter(code__in=list("DEFG")).select_related("recommended_entrance")]
        return Response({"barrels": barrels, "quick_places": [r for r in barrels if r["barrel_label"] == "A1"] + blocks})
    except DatabaseError:
        return Response({"detail": "Campus catalog unavailable."}, status=503)
