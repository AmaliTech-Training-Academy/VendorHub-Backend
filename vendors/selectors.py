from django.db.models import Prefetch

from accounts.models import VendorProfile
from products.models import Product

from .models import DeliveryWindow, Weekday


def vendor_list():
    # An open vendor has an active shop (VendorProfile.is_active) AND an active login (AppUser.is_active).
    return (
        VendorProfile.objects.filter(is_active=True, user__is_active=True)
        .prefetch_related(
            Prefetch(
                "delivery_windows",
                queryset=DeliveryWindow.objects.filter(is_active=True).order_by("sort_order", "start_time"),
                to_attr="active_delivery_windows",
            )
        )
        .order_by("id")
    )


def vendor_get(*, vendor_id):
    return vendor_list().filter(id=vendor_id).first()


def vendor_get_for_user(*, user):
    # The logged-in user's own active vendor profile, or None. Never takes an id from the request.
    profile = getattr(user, "vendor_profile", None)
    if profile is None:
        return None

    return vendor_get(vendor_id=profile.id)


def vendor_storefront_list():
    return vendor_list().prefetch_related(
        Prefetch(
            "products",
            queryset=_available_products().only("id", "vendor_id", "category"),
            to_attr="available_products",
        )
    )


def vendor_available_days(*, vendor):
    # Expects a vendor from vendor_list()/vendor_get(), which preload active_delivery_windows (no extra query).
    days = {day for window in vendor.active_delivery_windows for day in window.available_days}
    return Weekday.in_week_order(days)


def vendor_categories(*, vendor):
    # Expects a vendor from vendor_storefront_list(), which preloads available_products (no extra query).
    categories = {product.category.strip() for product in vendor.available_products if product.category}
    return sorted(category for category in categories if category)


def vendor_product_list(*, vendor_id):
    return _available_products().filter(vendor_id=vendor_id).order_by("id")


def _available_products():
    # What an employee can order: in stock, not deleted, and sold by an open vendor (same rule as vendor_list).
    return Product.objects.filter(
        in_stock=True,
        deleted_at__isnull=True,
        vendor__is_active=True,
        vendor__user__is_active=True,
    )
