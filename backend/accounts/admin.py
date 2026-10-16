from django.contrib import admin

from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "profile_type", "is_active", "is_staff", "date_joined")
    search_fields = ("email", "first_name", "last_name")
    list_filter = ("profile_type", "is_active", "is_staff")
    ordering = ("email",)
    fields = readonly_fields = (
        "email", "first_name", "last_name", "profile_type",
        "is_active", "is_staff", "is_superuser",
        "verified_affiliation", "university_email", "affiliation_verified_at",
        "affiliation_source", "email_two_factor", "date_joined", "last_login",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
