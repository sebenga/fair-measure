from django.contrib import admin

from .models import Comment, Post, PostMedia, Reaction


class PostMediaInline(admin.TabularInline):
    model = PostMedia
    extra = 0
    fields = ["media_asset", "display_order"]


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ["short_body", "author", "competition", "is_pinned", "is_deleted", "created_at"]
    list_filter = ["is_pinned", "is_announcement"]
    search_fields = ["body", "author__email", "competition__name"]
    autocomplete_fields = ["competition", "author", "fixture", "participant"]
    date_hierarchy = "created_at"
    inlines = [PostMediaInline]

    @admin.display(description="Body")
    def short_body(self, obj: Post) -> str:
        return (obj.body[:60] + "…") if len(obj.body) > 60 else (obj.body or "(media only)")

    @admin.display(boolean=True, description="Deleted", ordering="deleted_at")
    def is_deleted(self, obj: Post) -> bool:
        return obj.deleted_at is not None


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["short_body", "author", "post", "is_deleted", "created_at"]
    search_fields = ["body", "author__email"]
    autocomplete_fields = ["post", "author", "parent"]

    @admin.display(description="Body")
    def short_body(self, obj: Comment) -> str:
        return (obj.body[:60] + "…") if len(obj.body) > 60 else obj.body

    @admin.display(boolean=True, description="Deleted", ordering="deleted_at")
    def is_deleted(self, obj: Comment) -> bool:
        return obj.deleted_at is not None


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ["user", "kind", "post", "comment", "created_at"]
    list_filter = ["kind"]
    autocomplete_fields = ["user", "post", "comment"]
