from django.contrib import admin

from .models import (
    Fixture,
    FixtureLineup,
    FixtureSide,
    LineupEntry,
    MatchReport,
    ScoreEvent,
    Substitution,
)


class FixtureSideInline(admin.TabularInline):
    model = FixtureSide
    extra = 0
    fields = ["participant", "position", "is_home", "score", "outcome", "forfeited"]
    readonly_fields = ["score", "outcome"]
    autocomplete_fields = ["participant"]


class ScoreEventInline(admin.TabularInline):
    model = ScoreEvent
    extra = 0
    fields = ["side", "scoring_category", "quantity", "points", "minute", "player"]
    readonly_fields = ["points"]


@admin.register(Fixture)
class FixtureAdmin(admin.ModelAdmin):
    list_display = ["__str__", "competition", "status", "scheduled_at", "round_number"]
    list_filter = ["status", "competition"]
    search_fields = ["label", "location", "competition__name"]
    autocomplete_fields = ["competition", "stage"]
    date_hierarchy = "scheduled_at"
    inlines = [FixtureSideInline, ScoreEventInline]


@admin.register(ScoreEvent)
class ScoreEventAdmin(admin.ModelAdmin):
    list_display = ["fixture", "side", "scoring_category", "quantity", "points", "created_at"]
    list_filter = ["scoring_category"]
    search_fields = ["fixture__label", "note"]
    readonly_fields = ["points"]


class LineupEntryInline(admin.TabularInline):
    model = LineupEntry
    extra = 0
    fields = ["player", "role", "slot", "position", "number", "order"]


@admin.register(FixtureLineup)
class FixtureLineupAdmin(admin.ModelAdmin):
    list_display = ["side", "fixture", "formation", "captain"]
    inlines = [LineupEntryInline]


@admin.register(Substitution)
class SubstitutionAdmin(admin.ModelAdmin):
    list_display = ["fixture", "side", "player_off", "player_on", "minute", "reason"]


@admin.register(MatchReport)
class MatchReportAdmin(admin.ModelAdmin):
    list_display = ["fixture", "written_by", "submitted_at"]
