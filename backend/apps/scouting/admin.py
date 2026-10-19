from django.contrib import admin

from .models import (
    ConsentRecord,
    GuardianLink,
    HighlightVideo,
    InjuryRecord,
    Measurement,
    Organisation,
    PlayerProfile,
    PlayerSport,
    ScoutingRole,
)


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = ["name", "kind", "region"]
    search_fields = ["name"]


@admin.register(ScoutingRole)
class ScoutingRoleAdmin(admin.ModelAdmin):
    list_display = ["user", "role", "organisation", "team"]
    list_filter = ["role"]


class PlayerSportInline(admin.TabularInline):
    model = PlayerSport
    extra = 0


class MeasurementInline(admin.TabularInline):
    model = Measurement
    extra = 0


@admin.register(PlayerProfile)
class PlayerProfileAdmin(admin.ModelAdmin):
    list_display = ["first_name", "last_name", "date_of_birth", "visibility", "region"]
    list_filter = ["visibility", "gender_category", "region"]
    search_fields = ["first_name", "last_name"]
    inlines = [PlayerSportInline, MeasurementInline]


@admin.register(GuardianLink)
class GuardianLinkAdmin(admin.ModelAdmin):
    list_display = ["profile", "invited_email", "status"]


@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    list_display = ["profile", "given_as", "action", "visibility", "created_at"]
    readonly_fields = [field.name for field in ConsentRecord._meta.fields]

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


admin.site.register(InjuryRecord)
admin.site.register(HighlightVideo)
