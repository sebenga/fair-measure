from django.contrib import admin

from .models import Enquiry, Placement


@admin.register(Placement)
class PlacementAdmin(admin.ModelAdmin):
    list_display = ["name", "audience", "slot", "active", "display_order", "updated_at"]
    list_filter = ["audience", "slot", "active"]
    search_fields = ["name", "tagline", "body"]
    list_editable = ["active", "display_order"]


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = ["organisation", "audience", "contact_name", "email", "phone", "created_at"]
    list_filter = ["audience", "created_at"]
    search_fields = ["organisation", "contact_name", "email", "phone", "message"]
    readonly_fields = ["created_at", "updated_at"]
