from django.urls import path

from accounts.views import (
    current_user, google_link, google_sign_in, login, logout, profile, register, security,
    two_factor_email_code, two_factor_email_disable, two_factor_email_enable, two_factor_resend,
    two_factor_verify, verification,
    verification_cancel, verification_confirm, verification_start,
)
from core.views import health
from campus.views import search

urlpatterns = [
    path("api/campus/search/", search, name="campus-search"),
    path("api/health/", health, name="health"),
    path("api/auth/register/", register, name="register"),
    path("api/auth/login/", login, name="login"),
    path("api/auth/google/", google_sign_in, name="google-sign-in"),
    path("api/auth/two-factor/verify/", two_factor_verify, name="two-factor-verify"),
    path("api/auth/two-factor/resend/", two_factor_resend, name="two-factor-resend"),
    path("api/auth/logout/", logout, name="logout"),
    path("api/auth/me/", current_user, name="current-user"),
    path("api/auth/security/", security, name="security"),
    path("api/auth/security/google/", google_link, name="google-link"),
    path("api/auth/security/two-factor/email/code/", two_factor_email_code, name="two-factor-email-code"),
    path("api/auth/security/two-factor/email/enable/", two_factor_email_enable,
         name="two-factor-email-enable"),
    path("api/auth/security/two-factor/email/disable/", two_factor_email_disable,
         name="two-factor-email-disable"),
    path("api/profile/", profile, name="profile"),
    path("api/profile/verification/", verification, name="verification"),
    path("api/profile/verification/start/", verification_start, name="verification-start"),
    path("api/profile/verification/confirm/", verification_confirm, name="verification-confirm"),
    path("api/profile/verification/cancel/", verification_cancel, name="verification-cancel"),
]
