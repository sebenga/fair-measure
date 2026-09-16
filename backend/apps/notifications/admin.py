from django.contrib import admin

from .models import DeviceToken, Notification, NotificationPreference


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ["user", "platform", "device_name", "is_active", "last_seen_at"]
    list_filter = ["platform", "is_active"]
    search_fields = ["user__email", "token", "device_name"]
    autocomplete_fields = ["user"]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["user", "kind", "title", "is_read", "created_at"]
    list_filter = ["kind"]
    search_fields = ["user__email", "title", "body"]
    autocomplete_fields = ["user", "competition"]
    date_hierarchy = "created_at"

    @admin.display(boolean=True, description="Read", ordering="read_at")
    def is_read(self, obj: Notification) -> bool:
        return obj.read_at is not None


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "competition",
        "fixture_reminders",
        "score_updates",
        "feed_activity",
        "announcements",
    ]
    list_filter = ["fixture_reminders", "score_updates", "feed_activity", "announcements"]
    search_fields = ["user__email", "competition__name"]
    autocomplete_fields = ["user", "competition"]
