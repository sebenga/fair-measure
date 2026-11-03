from django.contrib import admin

from .models import Release


@admin.register(Release)
class ReleaseAdmin(admin.ModelAdmin):
    list_display = ["key", "kind", "live", "updated_by", "updated_at"]
    list_filter = ["kind", "live"]
    search_fields = ["key"]
    list_editable = ["live"]
    readonly_fields = ["updated_by", "created_at", "updated_at"]

    def save_model(self, request, obj, form, change) -> None:
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
