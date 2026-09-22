from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from .models import Product
from .selectors import product_get


def get_vendor_for_user(*, user, vendor_id):
    vendor_profile = getattr(user, "vendor_profile", None)

    if vendor_profile is None or vendor_profile.id != vendor_id:
        raise PermissionDenied(
            "You can only manage products for your own vendor account."
        )

    if not vendor_profile.is_active:
        raise PermissionDenied("Inactive vendors cannot manage products.")

    return vendor_profile


def get_owned_product(*, user, vendor_id, product_id):
    get_vendor_for_user(user=user, vendor_id=vendor_id)
    return product_get(vendor_id=vendor_id, product_id=product_id)


def product_create(*, vendor_id, user, **data):
    get_vendor_for_user(user=user, vendor_id=vendor_id)

    product = Product(
        vendor_id=vendor_id,
        **data,
    )
    product.full_clean()
    product.save()

    return product


def product_update(*, product, user, **data):
    get_vendor_for_user(user=user, vendor_id=product.vendor_id)

    for field, value in data.items():
        setattr(product, field, value)

    product.full_clean()
    product.save()

    return product


def product_delete(*, product, user):
    get_vendor_for_user(user=user, vendor_id=product.vendor_id)

    product.deleted_at = timezone.now()
    product.save(update_fields=["deleted_at"])