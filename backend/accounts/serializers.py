from collections.abc import Mapping

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.views.decorators.debug import sensitive_variables
from rest_framework import serializers

User = get_user_model()
DUPLICATE_EMAIL = "An account with this email already exists."
PROFILE_ONLY_FIELD = "Only profile_type is accepted."
INVALID_PROFILE_TYPE = "Choose Student, Staff, or Visitor."


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)

    @sensitive_variables()
    def to_internal_value(self, data):
        if (not isinstance(data, Mapping) or set(data) != {"email", "password"}
                or any(not isinstance(value, str) for value in data.values())):
            raise serializers.ValidationError("Invalid email or password.")
        return super().to_internal_value(data)


class ProfileSerializer(serializers.Serializer):
    """Accepts profile_type alone. Affiliation is descriptive and grants no permissions."""

    profile_type = serializers.ChoiceField(
        choices=User.ProfileType.choices,
        # The default message quotes the submitted value back to the client.
        error_messages={"invalid_choice": INVALID_PROFILE_TYPE},
    )

    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError({"non_field_errors": [PROFILE_ONLY_FIELD]})
        if set(data) != set(self.fields):
            raise serializers.ValidationError({"non_field_errors": [PROFILE_ONLY_FIELD]})
        # ChoiceField otherwise matches non-string values against the choice keys.
        if not isinstance(data["profile_type"], str):
            raise serializers.ValidationError({"profile_type": [INVALID_PROFILE_TYPE]})
        return super().to_internal_value(data)

    def update(self, instance, validated_data):
        # update_fields keeps the UPDATE to this one column; no privilege field is written.
        instance.profile_type = validated_data["profile_type"]
        instance.save(update_fields=["profile_type"])
        return instance


class RegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
    password_confirmation = serializers.CharField(
        write_only=True, trim_whitespace=False, max_length=128
    )

    @sensitive_variables()
    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unexpected = set(data) - set(self.fields)
            if unexpected:
                raise serializers.ValidationError({
                    "non_field_errors": ["Only email, password, and password_confirmation are accepted."]
                })
            # DRF CharField otherwise coerces numbers into strings.
            invalid = {key: ["Enter a string."] for key, value in data.items()
                       if not isinstance(value, str)}
            if invalid:
                raise serializers.ValidationError(invalid)
        return super().to_internal_value(data)

    def validate_email(self, value):
        value = User.objects.normalize_email(value.strip()).lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(DUPLICATE_EMAIL)
        return value

    @sensitive_variables()
    def validate(self, attrs):
        errors = {}
        if attrs["password"] != attrs["password_confirmation"]:
            errors["password_confirmation"] = ["Passwords do not match."]
        try:
            validate_password(attrs["password"], user=User(email=attrs["email"]))
        except ValidationError as error:
            errors["password"] = error.messages
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    @sensitive_variables()
    def create(self, validated_data):
        try:
            # A competing request may insert after validate_email's lookup.
            with transaction.atomic():
                return User.objects.create_user(
                    email=validated_data["email"], password=validated_data["password"]
                )
        except IntegrityError as error:
            constraint = getattr(getattr(error.__cause__, "diag", None), "constraint_name", None)
            if constraint in {"accounts_user_email_key", "accounts_user_email_ci_unique"}:
                raise serializers.ValidationError({"email": [DUPLICATE_EMAIL]}) from None
            raise
