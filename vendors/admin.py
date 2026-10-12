from django.contrib import admin

from .models import DeliveryWindow, VendorStorefront


@admin.register(DeliveryWindow)
class DeliveryWindowAdmin(admin.ModelAdmin):
    list_display = ["window_name", "vendor", "start_time", "end_time", "is_active", "sort_order"]
    list_filter = ["is_active"]


@admin.register(VendorStorefront)
class VendorStorefrontAdmin(admin.ModelAdmin):
    list_display = ["vendor", "slogan", "phone_number", "updated_at"]
