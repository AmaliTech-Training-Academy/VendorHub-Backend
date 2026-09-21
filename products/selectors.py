from .models import Product


def products_get(*, vendor_id):
    return Product.objects.filter(
        vendor_id=vendor_id,
        deleted_at__isnull=True,
    )