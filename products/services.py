from rest_framework.exceptions import PermissionDenied
from django.utils import timezone

from .models import Product


def product_create(*, vendor_id, user, **data):
    vendor_profile = getattr(user, "vendor_profile", None)

    if vendor_profile is None or vendor_profile.id != vendor_id:
        raise PermissionDenied(
            "You can only create products for your own vendor account."
        )

    product = Product(
        vendor_id=vendor_id,
        **data,
    )
    product.full_clean()
    product.save()

    return product


def product_update(*, product, user, **data):
    if product.vendor.user != user:
        raise PermissionDenied(
            "You can only modify your own products."
        )

    for field, value in data.items():
        setattr(product, field, value)

    product.full_clean()
    product.save()

    return product


def product_delete(*, product, user):
    if product.vendor.user != user:
        raise PermissionDenied(
            "You can only delete your own products."
        )

    product.deleted_at = timezone.now()
    product.save(update_fields=["deleted_at"])