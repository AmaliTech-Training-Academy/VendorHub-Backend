from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import models
from PIL import Image

MAX_IMAGE_SIZE_MB = 2
# Formats browsers display reliably. Checked on the decoded file, not the filename extension.
ALLOWED_IMAGE_FORMATS = {"PNG", "JPEG", "GIF", "WEBP"}


def product_image_path(product, filename):
    return f"products/{product.vendor_id}/{uuid4().hex}{Path(filename).suffix.lower()}"


def validate_image_size(image):
    if image.size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise ValidationError(f"Image must be {MAX_IMAGE_SIZE_MB} MB or smaller.")


def validate_image_format(image):
    image.seek(0)
    try:
        with Image.open(image) as decoded:
            image_format = decoded.format
    except Exception as e:
        raise ValidationError("Upload a valid image.") from e
    finally:
        image.seek(0)

    if image_format not in ALLOWED_IMAGE_FORMATS:
        raise ValidationError("Image must be PNG, JPG, GIF or WebP.")


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
    image = models.ImageField(upload_to=product_image_path, blank=True, validators=[validate_image_size, validate_image_format])
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
