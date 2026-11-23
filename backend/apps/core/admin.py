from django.contrib import admin

from .models import CompanyLegalDetails


@admin.register(CompanyLegalDetails)
class CompanyLegalDetailsAdmin(admin.ModelAdmin):
    list_display = ("legal_name", "registration_number", "email", "updated_at")
    readonly_fields = ("id", "created_at", "updated_at")

    def has_add_permission(self, request) -> bool:
        if CompanyLegalDetails.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
