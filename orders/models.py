from django.db import models


# Create your models here.

class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        DELIVERED = 'DELIVERED', 'Delivered'
        CANCELLED = 'CANCELLED', 'Cancelled'

    employee = models.ForeignKey(
        'accounts.EmployeeProfile',
        on_delete=models.PROTECT,
        related_name='orders',
    )

    vendor = models.ForeignKey(
        'accounts.VendorProfile',
        on_delete=models.PROTECT,
        related_name='orders',
    )

    delivery_window = models.ForeignKey(
        'vendors.DeliveryWindow',
        on_delete=models.PROTECT,
        related_name='orders',
    )

    delivery_date = models.DateField()

    order_code = models.CharField(
        max_length=255,
        unique=True,
    )

    selected_window_name = models.CharField(
        max_length=255,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    selected_start_time = models.TimeField()
    selected_end_time = models.TimeField()

    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    delivery_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(subtotal__gt=0),
                name="order_subtotal_gt_zero",
            ),
            models.CheckConstraint(
                condition=models.Q(total__gt=0),
                name="order_total_gt_zero",
            ),
            models.CheckConstraint(
                condition=models.Q(delivery_fee__gte=0),
                name="order_delivery_fee_gte_zero",
            ),
        ]

    def __str__(self):
        return self.order_code

class OrderItem(models.Model):
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.PROTECT,
        related_name='order_items',
    )

    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='order_items',
    )

    quantity = models.PositiveIntegerField()

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="order_item_quantity_gt_zero",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gt=0),
                name="order_item_unit_price_gt_zero",
            ),
            models.CheckConstraint(
                condition=models.Q(subtotal__gte=0),
                name="order_item_subtotal_gte_zero",
            ),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"