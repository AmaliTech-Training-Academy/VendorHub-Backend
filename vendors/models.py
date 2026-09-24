from django.db import models


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
