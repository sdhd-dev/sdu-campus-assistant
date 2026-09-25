from django.contrib.auth.password_validation import password_validators_help_texts
from django.db import DatabaseError
from django.middleware.csrf import get_token
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .serializers import RegistrationSerializer


class RegistrationAuthentication(SessionAuthentication):
    def authenticate(self, request):
        # DRF normally skips CSRF for anonymous requests; registration must not.
        self.enforce_csrf(request)
        return super().authenticate(request)


@sensitive_post_parameters("password", "password_confirmation")
@api_view(["GET", "POST"])
@authentication_classes([RegistrationAuthentication])
@permission_classes([AllowAny])
@sensitive_variables()
def register(request):
    headers = {"Cache-Control": "no-store"}
    if request.method == "GET":
        return Response({
            "csrf_token": get_token(request),
            "password_requirements": password_validators_help_texts(),
        }, headers=headers)

    try:
        serializer = RegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400, headers=headers)
        user = serializer.save()
    except DatabaseError:
        return Response(
            {"detail": "Registration is temporarily unavailable. Please try again."},
            status=503, headers=headers,
        )
    return Response({"email": user.email}, status=201, headers=headers)
