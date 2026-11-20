from django.db import DatabaseError
from django.views.decorators.cache import never_cache
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from accounts.views import CSRFAuthentication, UNAUTHENTICATED
from .places import place_data, places_queryset


@never_cache
@api_view(["GET"])
@authentication_classes([CSRFAuthentication])
@permission_classes([AllowAny])
def services(request):
    if not request.user.is_authenticated:
        return Response(UNAUTHENTICATED, status=401)
    slug = request.query_params.get("slug", "")
    if len(slug) > 80:
        return Response({"detail": "Service identifier is too long."}, status=400)
    try:
        queryset = places_queryset().filter(is_service=True)
        if slug:
            place = queryset.filter(slug=slug).first()
            if not place:
                return Response({"detail": "Service not found."}, status=404)
            return Response(place_data(place))
        return Response({"services": [place_data(p) for p in queryset.order_by("name")[:100]]})
    except DatabaseError:
        return Response({"detail": "Services are temporarily unavailable. Please retry."}, status=503)
