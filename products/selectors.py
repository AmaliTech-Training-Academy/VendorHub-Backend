from .models import Product


def products_get(*, vendor_id):
    return Product.objects.filter(
        vendor_id=vendor_id,
        vendor__is_active=True,
        deleted_at__isnull=True,
    ).order_by("id")


def product_get(*, vendor_id, product_id):
    return products_get(vendor_id=vendor_id).filter(id=product_id).first()