from django.contrib import admin

from .models import FantasyPick, FantasyTeam


class FantasyPickInline(admin.TabularInline):
    model = FantasyPick
    extra = 0
    raw_id_fields = ["player"]
    fields = ["player", "slot", "is_starter", "is_captain", "is_vice", "bench_order", "price"]


@admin.register(FantasyTeam)
class FantasyTeamAdmin(admin.ModelAdmin):
    list_display = ["name", "competition", "user", "created_at"]
    search_fields = ["name", "user__email", "competition__name"]
    autocomplete_fields = ["competition", "user"]
    inlines = [FantasyPickInline]
