from django.contrib import admin

from .models import Combination, Horse


@admin.register(Horse)
class HorseAdmin(admin.ModelAdmin):
    list_display = ["name", "registration_number", "breed", "sex", "status"]
    list_filter = ["status", "sex"]
    search_fields = ["name", "registration_number", "fei_id"]
    filter_horizontal = ["owners"]


@admin.register(Combination)
class CombinationAdmin(admin.ModelAdmin):
    list_display = ["participant", "horse", "rider", "rider_name", "trainer"]
