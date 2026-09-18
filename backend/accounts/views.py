from django.contrib.auth import (
    authenticate, get_user_model, login as session_login, logout as session_logout,
)
from django.contrib.auth.password_validation import password_validators_help_texts
from django.db import DatabaseError
from django.middleware.csrf import get_token
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.cache import never_cache
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .serializers import LoginSerializer, ProfileSerializer, RegistrationSerializer

User = get_user_model()
UNAUTHENTICATED = {"detail": "Authentication required."}


class CSRFAuthentication(SessionAuthentication):
    def authenticate(self, request):
        # DRF normally skips CSRF for anonymous requests, including login.
        self.enforce_csrf(request)
        return super().authenticate(request)


@sensitive_post_parameters("password", "password_confirmation")
@api_view(["GET", "POST"])
@authentication_classes([CSRFAuthentication])
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


@never_cache
@sensitive_post_parameters("password")
@api_view(["GET", "POST"])
@authentication_classes([CSRFAuthentication])
@permission_classes([AllowAny])
@sensitive_variables()
def login(request):
    if request.method == "GET":
        return Response({"csrf_token": get_token(request)})

    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"detail": "Invalid email or password."}, status=400)
    try:
        user = authenticate(request=request, **serializer.validated_data)
        if user is None or not user.is_active:
            return Response({"detail": "Invalid email or password."}, status=401)
        session_login(request, user)
    except DatabaseError:
        return Response({"detail": "Sign-in is temporarily unavailable. Please try again."}, status=503)
    # Django rotates the CSRF secret on login. Return a token for the new secret.
    return Response({"email": user.email, "csrf_token": get_token(request)})


@never_cache
@api_view(["POST"])
@authentication_classes([CSRFAuthentication])
@permission_classes([AllowAny])
def logout(request):
    # Also safe to repeat after a session has expired; CSRF is still required.
    session_logout(request)
    return Response(status=204)


@never_cache
@api_view(["GET"])
@authentication_classes([CSRFAuthentication])
@permission_classes([AllowAny])
def current_user(request):
    if not request.user.is_authenticated:
        return Response(UNAUTHENTICATED, status=401)
    return Response({"email": request.user.email, "csrf_token": get_token(request)})


@never_cache
@api_view(["GET", "PATCH"])
@authentication_classes([CSRFAuthentication])
@permission_classes([AllowAny])
def profile(request):
    # The account is taken from the session; the request body cannot name another user.
    if not request.user.is_authenticated:
        return Response(UNAUTHENTICATED, status=401)
    user = request.user
    if request.method == "PATCH":
        serializer = ProfileSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        try:
            user = serializer.update(user, serializer.validated_data)
        except DatabaseError:
            return Response(
                {"detail": "Saving your profile is temporarily unavailable. Please try again."},
                status=503,
            )
    return Response({
        "email": user.email,
        "profile_type": user.profile_type,
        "profile_types": [
            {"value": value, "label": label} for value, label in User.ProfileType.choices
        ],
        "csrf_token": get_token(request),
    })
