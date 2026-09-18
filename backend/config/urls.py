from django.urls import path

from accounts.views import register
from core.views import health

urlpatterns = [
    path("api/health/", health, name="health"),
    path("api/auth/register/", register, name="register"),
]
