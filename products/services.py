import logging

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from .models import Product
from .selectors import product_get

logger = logging.getLogger(__name__)


def get_vendor_for_user(user):
    vendor_profile = getattr(user, "vendor_profile", None)

    if vendor_profile is None:
        raise PermissionDenied("Only vendors can manage products.")

    if not vendor_profile.is_active:
        raise PermissionDenied("Inactive vendors cannot manage products.")

    return vendor_profile


def get_owned_product(*, user, product_id):
    vendor = get_vendor_for_user(user)
    return product_get(vendor_id=vendor.id, product_id=product_id)


def product_create(*, user, **data):
    vendor = get_vendor_for_user(user)

    product = Product(
        vendor=vendor,
        **data,
    )
    product.full_clean()
    product.save()

    return product


@transaction.atomic
def product_update(*, product, user, **data):
    vendor = get_vendor_for_user(user)
    if product.vendor_id != vendor.id:
        raise PermissionDenied("You can only modify your own products.")

    old_image = product.image.name

    for field, value in data.items():
        setattr(product, field, value)

    product.full_clean(exclude=None if "image" in data else ["image"])
    product.save()

    if "image" in data and old_image and old_image != product.image.name:
        storage = product.image.storage
        transaction.on_commit(lambda: delete_old_image(storage, old_image))

    return product


def delete_old_image(storage, name):
    try:
        storage.delete(name)
    except Exception:
        logger.exception("Could not delete old product image %s; the product update was saved.", name)


def product_delete(*, product, user):
    vendor = get_vendor_for_user(user)
    if product.vendor_id != vendor.id:
        raise PermissionDenied("You can only delete your own products.")

    product.deleted_at = timezone.now()
    product.save(update_fields=["deleted_at"])