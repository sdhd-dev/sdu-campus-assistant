from django.contrib import admin
from .models import Block, Entrance, Room, CampusPlace, DirectoryFaculty, Person, OfficeAssignment

@admin.register(CampusPlace)
class CampusPlaceAdmin(admin.ModelAdmin):
    list_display = ("slug", "name", "category", "verification_status", "verified_at")
    list_filter = ("category", "verification_status", "is_service")
    search_fields = ("slug", "name")
    def get_readonly_fields(self, request, obj=None):
        return ("slug",) if obj else ()

admin.site.register([Block, Entrance, Room])


class OfficeInline(admin.TabularInline):
    model = OfficeAssignment
    extra = 0
    autocomplete_fields = ("room",)


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("full_name", "role", "verification_status")
    list_filter = ("verification_status", "role", "offices__faculty")
    search_fields = ("full_name", "source_name")
    readonly_fields = ("search_name", "search_original", "search_transliterated")
    inlines = (OfficeInline,)

    def get_readonly_fields(self, request, obj=None):
        fields = ("search_name", "search_original", "search_transliterated")
        return fields + ("source_key",) if obj else fields


admin.site.unregister(Room)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    search_fields = ("code", "name")


admin.site.register(DirectoryFaculty)
