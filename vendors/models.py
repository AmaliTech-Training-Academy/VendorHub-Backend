from pathlib import Path
from uuid import uuid4
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

MAX_LOGO_SIZE_MB = 2


class Weekday(models.TextChoices):
    MONDAY = "MONDAY", "Monday"
    TUESDAY = "TUESDAY", "Tuesday"
    WEDNESDAY = "WEDNESDAY", "Wednesday"
    THURSDAY = "THURSDAY", "Thursday"
    FRIDAY = "FRIDAY", "Friday"
    SATURDAY = "SATURDAY", "Saturday"
    SUNDAY = "SUNDAY", "Sunday"

    @classmethod
    def in_week_order(cls, days):
        return sorted(set(days), key=cls.values.index)


class DeliveryWindow(models.Model):
    vendor = models.ForeignKey(
        "accounts.VendorProfile",
        related_name="delivery_windows",
        on_delete=models.CASCADE,
    )
    window_name = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()
    available_days = models.JSONField(default=list)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "start_time"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_time__gt=models.F("start_time")),
                name="delivery_window_end_after_start",
            ),
        ]

    def __str__(self):
        return f"{self.window_name} ({self.start_time:%H:%M}-{self.end_time:%H:%M})"


def storefront_logo_path(storefront, filename):
    return f"vendors/{storefront.vendor_id}/logo/{uuid4().hex}{Path(filename).suffix.lower()}"


def validate_logo_size(logo):
    if logo.size > MAX_LOGO_SIZE_MB * 1024 * 1024:
        raise ValidationError(f"Logo must be {MAX_LOGO_SIZE_MB} MB or smaller.")


class VendorStorefront(models.Model):

    vendor = models.OneToOneField(
        "accounts.VendorProfile",
        related_name="storefront",
        on_delete=models.CASCADE,
    )
    logo = models.ImageField(upload_to=storefront_logo_path, blank=True, validators=[validate_logo_size])
    slogan = models.CharField(max_length=150, blank=True)
    phone_number = models.CharField(
        max_length=16,
        blank=True,
        validators=[RegexValidator(r"^\+?[0-9]{7,15}$", "Enter a phone number of 7-15 digits, with an optional leading +.")],
    )
    address = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Storefront of {self.vendor}"
