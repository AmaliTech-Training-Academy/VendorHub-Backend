from accounts.models import VendorProfile
from products.models import Product


def vendor_list():
    return VendorProfile.objects.filter(is_active=True).order_by("id")


def vendor_get(*, vendor_id):
    return vendor_list().filter(id=vendor_id).first()


def vendor_product_list(*, vendor_id):
    return Product.objects.filter(
        vendor_id=vendor_id,
        in_stock=True,
        deleted_at__isnull=True,
    ).order_by("id")
