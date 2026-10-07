from django.contrib import admin
from .models import Block, Entrance, Room, CampusPlace

@admin.register(CampusPlace)
class CampusPlaceAdmin(admin.ModelAdmin):
    list_display = ("slug", "name", "category", "verification_status", "verified_at")
    list_filter = ("category", "verification_status")
    search_fields = ("slug", "name")
    def get_readonly_fields(self, request, obj=None):
        return ("slug",) if obj else ()

admin.site.register([Block, Entrance, Room])
