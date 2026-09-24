from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import DeliveryWindow, Weekday


@transaction.atomic
def delivery_settings_update(*, user, delivery_fee, available_days, time_windows):
    # The vendor always comes from the logged-in user, never from the request, so nobody can edit another vendor.
    vendor = getattr(user, "vendor_profile", None)
    if vendor is None:
        raise PermissionDenied("Only vendors can manage delivery settings.")
    if not vendor.is_active:
        raise PermissionDenied("Inactive vendors cannot manage delivery settings.")

    # Checked here too (not only in the API), like product price, so direct callers can't save a bad fee.
    vendor.delivery_fee = delivery_fee
    vendor.clean_fields(exclude=[field.name for field in vendor._meta.fields if field.name != "delivery_fee"])
    if vendor.delivery_fee < 0:
        raise ValidationError("Delivery fee cannot be negative.")

    vendor.save(update_fields=["delivery_fee", "updated_at"])

    # The vendor picks one set of days; every window is stored with that same set.
    days = Weekday.in_week_order(available_days)
    existing = {window.id: window for window in vendor.delivery_windows.all()}
    kept_ids = []

    for sort_order, data in enumerate(time_windows):
        window_id = data.get("id")
        if window_id is None:
            window = DeliveryWindow(vendor=vendor)
        elif window_id in existing:
            window = existing[window_id]
        else:
            raise ValidationError(f"Delivery window {window_id} does not belong to this vendor.")

        window.window_name = data["window_name"]
        window.start_time = data["start_time"]
        window.end_time = data["end_time"]
        window.available_days = days
        window.sort_order = sort_order
        window.is_active = True
        window.full_clean()
        window.save()
        kept_ids.append(window.id)

    # Windows left out are deactivated, not deleted, so past orders that reference them stay valid.
    vendor.delivery_windows.filter(is_active=True).exclude(id__in=kept_ids).update(
        is_active=False,
        updated_at=timezone.now(),
    )

    return vendor
