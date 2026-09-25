from django.urls import path

from accounts.views import current_user, login, logout, register
from core.views import health

urlpatterns = [
    path("api/health/", health, name="health"),
    path("api/auth/register/", register, name="register"),
    path("api/auth/login/", login, name="login"),
    path("api/auth/logout/", logout, name="logout"),
    path("api/auth/me/", current_user, name="current-user"),
]
