from django.contrib import admin

from .models import DeliveryWindow


@admin.register(DeliveryWindow)
class DeliveryWindowAdmin(admin.ModelAdmin):
    list_display = ["window_name", "vendor", "start_time", "end_time", "is_active", "sort_order"]
    list_filter = ["is_active"]
