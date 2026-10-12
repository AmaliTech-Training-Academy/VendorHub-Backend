from .models import Product
from accounts.models import VendorProfile


def products_get(*, vendor_id):
    return Product.objects.filter(
    vendor_id=vendor_id,
    vendor__verification_status=VendorProfile.VerificationStatus.APPROVED,
    deleted_at__isnull=True,
).order_by("id")


def product_get(*, vendor_id, product_id):
    return products_get(vendor_id=vendor_id).filter(id=product_id).first()
