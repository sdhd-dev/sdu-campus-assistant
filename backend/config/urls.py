from django.urls import path

from accounts.views import (
    current_user, google_link, google_sign_in, login, logout, profile, register, security,
    two_factor_disable, two_factor_enable, two_factor_setup, two_factor_verify,
)
from core.views import health

urlpatterns = [
    path("api/health/", health, name="health"),
    path("api/auth/register/", register, name="register"),
    path("api/auth/login/", login, name="login"),
    path("api/auth/google/", google_sign_in, name="google-sign-in"),
    path("api/auth/two-factor/verify/", two_factor_verify, name="two-factor-verify"),
    path("api/auth/logout/", logout, name="logout"),
    path("api/auth/me/", current_user, name="current-user"),
    path("api/auth/security/", security, name="security"),
    path("api/auth/security/google/", google_link, name="google-link"),
    path("api/auth/security/two-factor/setup/", two_factor_setup, name="two-factor-setup"),
    path("api/auth/security/two-factor/enable/", two_factor_enable, name="two-factor-enable"),
    path("api/auth/security/two-factor/disable/", two_factor_disable, name="two-factor-disable"),
    path("api/profile/", profile, name="profile"),
]
