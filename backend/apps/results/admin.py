from django.contrib import admin

from .models import CompetitionOfficial, EntryResult, ResultAmendment, ResultSheet


@admin.register(CompetitionOfficial)
class CompetitionOfficialAdmin(admin.ModelAdmin):
    list_display = ["competition", "user", "title"]
    list_filter = ["title"]


@admin.register(ResultSheet)
class ResultSheetAdmin(admin.ModelAdmin):
    list_display = ["fixture", "finalised_at", "finalised_by"]


@admin.register(EntryResult)
class EntryResultAdmin(admin.ModelAdmin):
    list_display = ["side", "rank", "status", "computed_status", "primary", "welfare_locked"]


@admin.register(ResultAmendment)
class ResultAmendmentAdmin(admin.ModelAdmin):
    list_display = ["fixture", "action", "actor", "reason", "created_at"]
    readonly_fields = [field.name for field in ResultAmendment._meta.fields]

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
