import secrets
import time
from functools import wraps

from django.contrib.auth import (
    authenticate, get_user_model, login as session_login, logout as session_logout,
)
from django.contrib.auth.password_validation import password_validators_help_texts
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import DatabaseError, IntegrityError, transaction
from django.middleware.csrf import get_token
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.cache import never_cache
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import google, two_factor, university
from .serializers import LoginSerializer, ProfileSerializer, RegistrationSerializer

User = get_user_model()
UNAUTHENTICATED = {"detail": "Authentication required."}
PENDING_2FA = "two_factor_pending"
PENDING_2FA_SECONDS = 300
GOOGLE_NONCE = "google_nonce"
INVALID_CODE = {"detail": "That code isn’t valid. Check your authenticator app and try again."}
LOCKED_CODE = {"detail": "Too many incorrect codes. Wait a few minutes and try again."}
GOOGLE_INVALID = {"detail": "Google sign-in couldn’t be verified. Please try again."}
GOOGLE_UNAVAILABLE = {"detail": "Google sign-in is temporarily unavailable. Please try again."}
GOOGLE_DISABLED = {"detail": "Google sign-in isn’t configured for this server."}


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
        return complete_sign_in(request, user)
    except DatabaseError:
        return Response({"detail": "Sign-in is temporarily unavailable. Please try again."}, status=503)


def complete_sign_in(request, user):
    """Signs the user in, or holds them at the second step when 2FA is on."""
    if user.two_factor_enabled:
        # The first factor passed, but the session stays anonymous until the code is checked.
        request.session.cycle_key()
        request.session[PENDING_2FA] = {
            "user": user.pk, "expires": int(time.time()) + PENDING_2FA_SECONDS,
        }
        return Response({"two_factor_required": True, "csrf_token": get_token(request)})
    request.session.pop(PENDING_2FA, None)
    request.session.pop(GOOGLE_NONCE, None)
    session_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    # Django rotates the CSRF secret on login. Return a token for the new secret.
    return Response({"email": user.email, "csrf_token": get_token(request)})


def code_from(request):
    if not isinstance(request.data, dict) or set(request.data) != {"code"}:
        return None
    code = request.data["code"]
    return code if isinstance(code, str) and len(code) <= 32 else None


@never_cache
@api_view(["POST"])
@authentication_classes([CSRFAuthentication])
@permission_classes([AllowAny])
@sensitive_variables()
def two_factor_verify(request):
    pending = request.session.get(PENDING_2FA)
    if not isinstance(pending, dict) or pending.get("expires", 0) < time.time():
        request.session.pop(PENDING_2FA, None)
        return Response({"detail": "Your sign-in expired. Please sign in again."}, status=401)
    code = code_from(request)
    if code is None:
        return Response(INVALID_CODE, status=400)
    try:
        user = User.objects.filter(pk=pending.get("user"), is_active=True).first()
        if user is None or not user.two_factor_enabled:
            request.session.pop(PENDING_2FA, None)
            return Response({"detail": "Your sign-in expired. Please sign in again."}, status=401)
        result = two_factor.check_code(user, code)
        if result == two_factor.LOCKED:
            return Response(LOCKED_CODE, status=429)
        if result != two_factor.OK:
            return Response(INVALID_CODE, status=400)
        request.session.pop(PENDING_2FA)
        session_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    except DatabaseError:
        return Response({"detail": "Sign-in is temporarily unavailable. Please try again."}, status=503)
    return Response({"email": user.email, "csrf_token": get_token(request)})


def google_nonce(request):
    nonce = request.session.get(GOOGLE_NONCE)
    if not isinstance(nonce, str):
        nonce = request.session[GOOGLE_NONCE] = secrets.token_urlsafe(32)
    return nonce


def verified_google_identity(request):
    """Returns (identity, None) or (None, error response)."""
    if not google.client_id():
        return None, Response(GOOGLE_DISABLED, status=404)
    if not isinstance(request.data, dict) or set(request.data) != {"credential"}:
        return None, Response(GOOGLE_INVALID, status=400)
    try:
        identity = google.verify_credential(
            request.data["credential"], request.session.get(GOOGLE_NONCE),
        )
    except google.GoogleUnavailable:
        return None, Response(GOOGLE_UNAVAILABLE, status=503)
    except google.InvalidGoogleCredential:
        return None, Response(GOOGLE_INVALID, status=400)
    return identity, None


@never_cache
@sensitive_post_parameters("credential")
@api_view(["GET", "POST"])
@authentication_classes([CSRFAuthentication])
@permission_classes([AllowAny])
def google_sign_in(request):
    if request.method == "GET":
        client = google.client_id()
        return Response({
            "client_id": client,
            "nonce": google_nonce(request) if client else None,
            "csrf_token": get_token(request),
        })

    identity, error = verified_google_identity(request)
    if error:
        return error
    try:
        user = User.objects.filter(google_subject=identity["subject"]).first()
        if user is None:
            if User.objects.filter(email__iexact=identity["email"]).exists():
                # Registration does not prove email ownership, so an existing account is
                # never joined automatically; its owner connects Google from the profile.
                return Response({
                    "detail": "An account with this email already exists. Sign in with your "
                              "password, then connect Google from your profile.",
                }, status=409)
            try:
                with transaction.atomic():
                    # No password: this account signs in with Google only.
                    user = User.objects.create_user(
                        identity["email"], None, google_subject=identity["subject"],
                    )
            except IntegrityError:
                return Response({"detail": "This account already exists. Please try again."}, status=409)
        if not user.is_active:
            return Response(GOOGLE_INVALID, status=401)
        return complete_sign_in(request, user)
    except DatabaseError:
        return Response({"detail": "Sign-in is temporarily unavailable. Please try again."}, status=503)


def security_state(request, user, **extra):
    return Response({
        "google_available": bool(google.client_id()),
        "google_linked": user.google_linked,
        "has_password": user.has_usable_password(),
        "two_factor_enabled": user.two_factor_enabled,
        "recovery_codes_remaining": (
            two_factor.recovery_codes_remaining(user) if user.two_factor_enabled else 0
        ),
        "csrf_token": get_token(request),
        **extra,
    })


@never_cache
@api_view(["GET"])
@authentication_classes([CSRFAuthentication])
@permission_classes([AllowAny])
def security(request):
    if not request.user.is_authenticated:
        return Response(UNAUTHENTICATED, status=401)
    return security_state(request, request.user)


@never_cache
@sensitive_post_parameters("credential")
@api_view(["POST", "DELETE"])
@authentication_classes([CSRFAuthentication])
@permission_classes([AllowAny])
def google_link(request):
    if not request.user.is_authenticated:
        return Response(UNAUTHENTICATED, status=401)
    user = request.user
    try:
        if request.method == "DELETE":
            if not user.has_usable_password():
                return Response({
                    "detail": "This account signs in only with Google, so Google can’t be disconnected.",
                }, status=400)
            user.google_subject = None
            user.save(update_fields=["google_subject"])
            return security_state(request, user)

        identity, error = verified_google_identity(request)
        if error:
            return error
        if user.google_subject == identity["subject"]:
            return security_state(request, user)
        if user.google_subject:
            return Response({"detail": "Disconnect the current Google account first."}, status=409)
        taken = User.objects.filter(google_subject=identity["subject"]).exclude(pk=user.pk)
        if taken.exists():
            return Response({
                "detail": "This Google account is already connected to another campus account.",
            }, status=409)
        try:
            with transaction.atomic():
                user.google_subject = identity["subject"]
                user.save(update_fields=["google_subject"])
        except IntegrityError:
            user.google_subject = None
            return Response({
                "detail": "This Google account is already connected to another campus account.",
            }, status=409)
    except DatabaseError:
        return Response({"detail": "Saving is temporarily unavailable. Please try again."}, status=503)
    return security_state(request, user)


@never_cache
@api_view(["POST"])
@authentication_classes([CSRFAuthentication])
@permission_classes([AllowAny])
def two_factor_setup(request):
    if not request.user.is_authenticated:
        return Response(UNAUTHENTICATED, status=401)
    if request.data:
        return Response({"detail": "No fields are accepted."}, status=400)
    try:
        setup = two_factor.start_setup(request.user)
    except DatabaseError:
        return Response({"detail": "Saving is temporarily unavailable. Please try again."}, status=503)
    if setup is None:
        return Response({"detail": "Two-factor authentication is already on."}, status=409)
    return Response({**setup, "csrf_token": get_token(request)})


@never_cache
@api_view(["POST"])
@authentication_classes([CSRFAuthentication])
@permission_classes([AllowAny])
@sensitive_variables()
def two_factor_enable(request):
    if not request.user.is_authenticated:
        return Response(UNAUTHENTICATED, status=401)
    code = code_from(request)
    if code is None:
        return Response(INVALID_CODE, status=400)
    try:
        result, codes = two_factor.confirm_setup(request.user, code)
    except DatabaseError:
        return Response({"detail": "Saving is temporarily unavailable. Please try again."}, status=503)
    if result == two_factor.LOCKED:
        return Response(LOCKED_CODE, status=429)
    if result != two_factor.OK:
        return Response(INVALID_CODE, status=400)
    # Recovery codes are shown once; only their digests are stored.
    return security_state(request, request.user, recovery_codes=codes)


@never_cache
@api_view(["POST"])
@authentication_classes([CSRFAuthentication])
@permission_classes([AllowAny])
@sensitive_variables()
def two_factor_disable(request):
    if not request.user.is_authenticated:
        return Response(UNAUTHENTICATED, status=401)
    code = code_from(request)
    if code is None:
        return Response(INVALID_CODE, status=400)
    try:
        result = two_factor.disable(request.user, code)
    except DatabaseError:
        return Response({"detail": "Saving is temporarily unavailable. Please try again."}, status=503)
    if result == two_factor.LOCKED:
        return Response(LOCKED_CODE, status=429)
    if result != two_factor.OK:
        return Response(INVALID_CODE, status=400)
    return security_state(request, request.user)


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


UNIVERSITY_DISABLED = {"detail": "University email verification isn’t configured for this server."}
UNIVERSITY_ONLY = {"detail": "Enter your SDU student or staff email address."}
UNIVERSITY_SENT = "If this address can be verified, we sent a 6-digit code to it."
UNIVERSITY_RESULTS = {
    university.INVALID: (400, "That code isn’t valid. Check the email and try again."),
    university.EXPIRED: (400, "This code has expired. Request a new one."),
    university.NO_CODE: (400, "Request a new code first."),
    university.LOCKED: (429, "Too many incorrect codes. Request a new one."),
    university.NOT_UNIVERSITY: (400, UNIVERSITY_ONLY["detail"]),
    university.TAKEN: (409, "This university email is already verified for another account."),
}
UNIVERSITY_UNAVAILABLE = {"detail": "Verification is temporarily unavailable. Please try again."}


def verification_state(request, user, status=200, **extra):
    return Response({
        **university.state(user), "csrf_token": get_token(request), **extra,
    }, status=status)


def university_email_from(request):
    """Returns a normalized address on a configured university domain, or None."""
    if not isinstance(request.data, dict) or set(request.data) != {"email"}:
        return None
    email = request.data["email"]
    if not isinstance(email, str) or len(email) > 254:
        return None
    email = User.objects.normalize_email(email.strip()).lower()
    try:
        validate_email(email)
    except ValidationError:
        return None
    return email if university.affiliation_for_email(email) else None


def university_request(view):
    """Session, feature switch, and database errors shared by the verification views."""
    @wraps(view)
    def wrapper(request):
        if not request.user.is_authenticated:
            return Response(UNAUTHENTICATED, status=401)
        if not university.enabled():
            return Response(UNIVERSITY_DISABLED, status=404)
        try:
            return view(request, request.user)
        except (DatabaseError, university.MailUnavailable):
            return Response(UNIVERSITY_UNAVAILABLE, status=503)
    return wrapper


@never_cache
@api_view(["GET", "DELETE"])
@authentication_classes([CSRFAuthentication])
@permission_classes([AllowAny])
@university_request
def verification(request, user):
    if request.method == "DELETE":
        university.remove(user)
    return verification_state(request, user)


@never_cache
@api_view(["POST"])
@authentication_classes([CSRFAuthentication])
@permission_classes([AllowAny])
@university_request
def verification_start(request, user):
    email = university_email_from(request)
    if email is None:
        return Response(UNIVERSITY_ONLY, status=400)
    result, retry_after = university.start(user, email)
    if result == university.RATE_LIMITED:
        return verification_state(
            request, user, status=429, retry_after=retry_after,
            detail="Please wait before requesting another code.",
        )
    return verification_state(request, user, detail=UNIVERSITY_SENT)


@never_cache
@api_view(["POST"])
@authentication_classes([CSRFAuthentication])
@permission_classes([AllowAny])
@university_request
@sensitive_variables()
def verification_confirm(request, user):
    code = code_from(request)
    result = university.confirm(user, code) if code is not None else university.INVALID
    if result != university.OK:
        status, detail = UNIVERSITY_RESULTS[result]
        return verification_state(request, user, status=status, detail=detail)
    return verification_state(request, user)


@never_cache
@api_view(["POST"])
@authentication_classes([CSRFAuthentication])
@permission_classes([AllowAny])
@university_request
def verification_cancel(request, user):
    university.cancel(user)
    return verification_state(request, user)
