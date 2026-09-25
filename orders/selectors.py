from accounts.models import VendorProfile
from orders.models import Order
from products.models import Product
from vendors.models import DeliveryWindow


def active_vendor_get(*, vendor_id):
    return VendorProfile.objects.filter(
        id=vendor_id,
        is_active=True,
    ).first()


def delivery_window_get(*, delivery_window_id):
    return (
        DeliveryWindow.objects.filter(
            id=delivery_window_id,
            is_active=True,
        )
        .select_related("vendor")
        .first()
    )


def order_products_get(*, product_ids):
    return Product.objects.filter(
        id__in=product_ids,
    )


def order_get(*, order_id):
    return (
        Order.objects.select_related(
            "employee",
            "vendor",
            "delivery_window",
        )
        .prefetch_related(
            "order_items__product",
        )
        .filter(id=order_id)
        .first()
    )