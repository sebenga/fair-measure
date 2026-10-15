from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import SocialAccount, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["-date_joined"]
    list_display = ["email", "display_name", "is_active", "is_staff", "date_joined"]
    list_filter = ["is_active", "is_staff", "is_superuser", "email_verified"]
    search_fields = ["email", "display_name", "given_name", "family_name"]
    readonly_fields = ["date_joined", "last_login", "updated_at"]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("display_name", "avatar_url", "bio")}),
        (
            "Personal details",
            {
                "fields": (
                    "given_name",
                    "family_name",
                    "date_of_birth",
                    "id_number",
                    "phone",
                    "city",
                    "country",
                    "headline",
                    "website",
                    "experience",
                    "education",
                    "skills",
                    "languages",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "email_verified",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Dates", {"fields": ("last_login", "date_joined", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "display_name", "password1", "password2"),
            },
        ),
    )


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = ["provider", "provider_user_id", "user", "created_at"]
    list_filter = ["provider"]
    search_fields = ["provider_user_id", "user__email"]
    raw_id_fields = ["user"]
