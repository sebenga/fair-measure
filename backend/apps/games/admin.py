from django.contrib import admin

from .models import NOC, Athlete, Entry, Games, GamesEvent, Medal, MedalChange


@admin.register(Games)
class GamesAdmin(admin.ModelAdmin):
    list_display = ["name", "kind", "host", "starts_on", "medal_table_ranking", "status"]


@admin.register(NOC)
class NOCAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "games"]


@admin.register(Athlete)
class AthleteAdmin(admin.ModelAdmin):
    list_display = ["name", "noc", "games"]


@admin.register(GamesEvent)
class GamesEventAdmin(admin.ModelAdmin):
    list_display = ["sport_label", "name", "gender", "medal_type", "status", "games"]
    list_filter = ["sport_label", "status"]


admin.site.register(Entry)
admin.site.register(Medal)


@admin.register(MedalChange)
class MedalChangeAdmin(admin.ModelAdmin):
    list_display = ["event", "reason", "created_at"]
    readonly_fields = [field.name for field in MedalChange._meta.fields]

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
