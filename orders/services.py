from decimal import Decimal
from uuid import uuid4
from accounts.models import EmployeeProfile

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from orders.models import Order, OrderItem
from orders.selectors import (
    active_vendor_get,
    delivery_window_get,
    order_products_get,
)
from vendors.models import Weekday


def _employee_context(*, user):
    if not user.is_authenticated:
        raise PermissionDenied(
            "Authentication is required to place an order."
        )

    if user.role != "EMPLOYEE":
        raise PermissionDenied("Only employees can place orders.")
    try:
        return user.employee_profile
    except EmployeeProfile.DoesNotExist:
        raise PermissionDenied("Employee profile is required to place an order.")
    


def _validated_products(*, vendor, items):
    product_ids = [item["product_id"] for item in items]

    if len(product_ids) != len(set(product_ids)):
        raise ValidationError(
            "Duplicate products are not allowed in one order."
        )

    products = list(order_products_get(product_ids=product_ids))
    products_by_id = {product.id: product for product in products}

    for item in items:
        product = products_by_id.get(item["product_id"])

        if product is None:
            raise ValidationError("Product not found.")

        if product.vendor_id != vendor.id:
            raise ValidationError(
                "Product belongs to another vendor."
            )

        if product.deleted_at is not None:
            raise ValidationError("Product has been deleted.")

        if not product.in_stock:
            raise ValidationError("Product is out of stock.")

    return products_by_id


@transaction.atomic
def order_create(
    *,
    user,
    vendor_id,
    items,
    selected_delivery_window,
    delivery_date,
):
    vendor = active_vendor_get(vendor_id=vendor_id)

    if vendor is None:
        raise ValidationError("Vendor not found or inactive.")

    employee = _employee_context(user=user)

    delivery_window = delivery_window_get(
        delivery_window_id=selected_delivery_window,
    )

    if delivery_window is None:
        raise ValidationError("Delivery window not found.")

    today = timezone.localdate()

    if delivery_date < today:
        raise ValidationError(
            "Delivery date cannot be in the past."
        )

    weekday = Weekday.values[delivery_date.weekday()]

    if weekday not in delivery_window.available_days:
        raise ValidationError(
            "Selected delivery window is not available on this date."
        )

    if (
        delivery_date == today
        and timezone.localtime().time() >= delivery_window.start_time
    ):
        raise ValidationError(
            "Selected delivery window has already started today."
        )

    if delivery_window.vendor_id != vendor.id:
        raise ValidationError(
            "Delivery window does not belong to the selected vendor."
        )

    products_by_id = _validated_products(
        vendor=vendor,
        items=items,
    )

    subtotal = Decimal("0.00")
    order_items = []

    for item in items:
        product = products_by_id[item["product_id"]]
        unit_price = product.price
        line_subtotal = unit_price * item["quantity"]

        subtotal += line_subtotal

        order_items.append(
            OrderItem(
                product=product,
                quantity=item["quantity"],
                unit_price=unit_price,
                subtotal=line_subtotal,
            )
        )

    delivery_fee = vendor.delivery_fee or Decimal("0.00")
    total_amount = subtotal + delivery_fee
    if total_amount > Decimal("999999999.99"):
        raise ValidationError(
            "Order total exceeds the maximum amount."
        )

    order = Order.objects.create(
        employee=employee,
        vendor=vendor,
        delivery_window=delivery_window,
        delivery_date=delivery_date,
        order_code=f"VH-{timezone.now():%Y%m%d}-{uuid4().hex[:8].upper()}",
        selected_window_name=delivery_window.window_name,
        selected_start_time=delivery_window.start_time,
        selected_end_time=delivery_window.end_time,
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        total=total_amount,
        status=Order.Status.PENDING,
    )

    for order_item in order_items:
        order_item.order = order

    OrderItem.objects.bulk_create(order_items)

    return order
