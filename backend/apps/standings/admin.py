from django.contrib import admin

from .models import StandingRow


@admin.register(StandingRow)
class StandingRowAdmin(admin.ModelAdmin):
    list_display = ["competition", "position", "participant", "played", "points", "computed_at"]
    list_filter = ["competition"]
    search_fields = ["participant__name", "competition__name"]
    readonly_fields = [field.name for field in StandingRow._meta.fields]

    def has_add_permission(self, request) -> bool:
        # Rows are derived from fixtures; editing them by hand would be undone
        # by the next recompute.
        return False
