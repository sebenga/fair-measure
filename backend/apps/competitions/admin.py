from django.contrib import admin

from .models import (
    Competition,
    Membership,
    Participant,
    PointsPolicy,
    RosterMember,
    Rule,
    ScoringCategory,
    Stage,
)


class ScoringCategoryInline(admin.TabularInline):
    model = ScoringCategory
    extra = 0
    fields = ["name", "code", "points", "affects_score", "display_order"]


class RuleInline(admin.TabularInline):
    model = Rule
    extra = 0
    fields = ["name", "display_order"]


class PointsPolicyInline(admin.StackedInline):
    model = PointsPolicy
    can_delete = False
    extra = 0


class StageInline(admin.TabularInline):
    model = Stage
    extra = 0
    fields = ["name", "kind", "display_order", "advances_count"]


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ["user"]
    fields = ["user", "role", "created_at"]
    readonly_fields = ["created_at"]


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "sport",
        "format",
        "status",
        "owner",
        "is_private",
        "show_on_landing",
        "created_at",
    ]
    list_filter = ["status", "format", "is_private", "show_on_landing", "sport"]
    search_fields = ["name", "slug", "description", "owner__email"]
    autocomplete_fields = ["owner"]
    prepopulated_fields = {"slug": ["name"]}
    date_hierarchy = "created_at"
    inlines = [PointsPolicyInline, ScoringCategoryInline, RuleInline, StageInline, MembershipInline]


class RosterMemberInline(admin.TabularInline):
    model = RosterMember
    extra = 0
    fields = ["name", "number", "position", "user", "is_active"]
    autocomplete_fields = ["user"]


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ["name", "competition", "seed", "is_active"]
    list_filter = ["is_active", "competition"]
    search_fields = ["name", "short_name"]
    autocomplete_fields = ["competition", "managed_by"]
    inlines = [RosterMemberInline]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "competition", "role", "created_at"]
    list_filter = ["role"]
    search_fields = ["user__email", "competition__name"]
    autocomplete_fields = ["user", "competition"]


@admin.register(ScoringCategory)
class ScoringCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "competition", "points", "affects_score", "display_order"]
    list_filter = ["affects_score"]
    search_fields = ["name", "code", "competition__name"]
    autocomplete_fields = ["competition"]


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ["name", "competition", "kind", "display_order"]
    list_filter = ["kind"]
    search_fields = ["name", "competition__name"]
    autocomplete_fields = ["competition"]
