from django.contrib import admin

from .models import MediaAsset


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = ["id", "kind", "status", "owner", "competition", "size_bytes", "created_at"]
    list_filter = ["kind", "status"]
    search_fields = ["id", "storage_key", "provider_asset_id", "owner__email"]
    autocomplete_fields = ["owner", "competition"]
    readonly_fields = ["storage_key", "provider_asset_id", "playback_id", "ready_at"]
    date_hierarchy = "created_at"
