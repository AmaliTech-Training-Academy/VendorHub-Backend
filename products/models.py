from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import models

MAX_IMAGE_SIZE_MB = 2


def product_image_path(product, filename):
    return f"products/{product.vendor_id}/{uuid4().hex}{Path(filename).suffix.lower()}"


def validate_image_size(image):
    if image.size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise ValidationError(f"Image must be {MAX_IMAGE_SIZE_MB} MB or smaller.")


class Product(models.Model):
    vendor = models.ForeignKey(
        "accounts.VendorProfile",
        related_name="products",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    description = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=255, blank=True, null=True)
    image = models.ImageField(upload_to=product_image_path, blank=True, validators=[validate_image_size])
    in_stock = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price__gt=0),
                name="product_price_gt_zero",
            ),
        ]

    def __str__(self):
        return self.name
