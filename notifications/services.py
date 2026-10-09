import logging

import requests
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def send_email(*, recipient, subject, template, context):
    config = settings.BREVO
    if not config.get("API_KEY") or not config.get("SENDER_EMAIL"):
        logger.error("Brevo email skipped because API key or sender email is missing")
        return False

    html = render_to_string(template, context)
    payload = {
        "sender": {
            "name": config.get("SENDER_NAME", "VendorHub"),
            "email": config["SENDER_EMAIL"],
        },
        "to": [{"email": recipient}],
        "subject": subject,
        "htmlContent": html,
        "textContent": strip_tags(html),
    }
    try:
        response = requests.post(
            f'{config["API_URL"].rstrip("/")}/smtp/email',
            json=payload,
            headers={"api-key": config["API_KEY"]},
            timeout=(3, 10),
        )
        if not response.ok:
            logger.warning(
                "Brevo rejected email (HTTP %s): %s",
                response.status_code,
                response.text[:500],
            )
            return False
        data = response.json() if response.content else {}
    except (requests.RequestException, ValueError):
        logger.exception("Brevo email delivery failed for %s", recipient)
        return False

    if not isinstance(data, dict):
        logger.error("Brevo returned an invalid email response")
        return False
    return True


def _vendor_context(vendor):
    return {
        "vendor_name": vendor.owner_name,
        "business_name": vendor.business_name,
        "support_email": settings.BREVO["SUPPORT_EMAIL"],
    }


def send_vendor_pending(vendor):
    try:
        return send_email(
            recipient=vendor.user.email,
            subject="Your VendorHub account is pending verification",
            template="notifications/vendor_pending.html",
            context=_vendor_context(vendor),
        )
    except Exception:
        logger.exception("Pending vendor email failed for vendor %s", vendor.pk)
        return False


def send_vendor_approved(vendor):
    try:
        return send_email(
            recipient=vendor.user.email,
            subject="Your VendorHub account has been approved",
            template="notifications/vendor_approved.html",
            context=_vendor_context(vendor),
        )
    except Exception:
        logger.exception("Approved vendor email failed for vendor %s", vendor.pk)
        return False


def send_vendor_declined(vendor):
    try:
        return send_email(
            recipient=vendor.user.email,
            subject="Your VendorHub account was declined",
            template="notifications/vendor_declined.html",
            context={**_vendor_context(vendor), "reason": vendor.decline_reason},
        )
    except Exception:
        logger.exception("Declined vendor email failed for vendor %s", vendor.pk)
        return False


def _order_context(order):
    items = [
        {
            "name": item.product.name,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "subtotal": item.subtotal,
        }
        for item in order.order_items.select_related("product").all()
    ]
    return {
        "order_code": order.order_code,
        "business_name": order.vendor.business_name,
        "vendor_name": order.vendor.owner_name,
        "employee_name": order.employee.full_name,
        "delivery_date": order.delivery_date,
        "window_name": order.selected_window_name,
        "items": items,
        "subtotal": order.subtotal,
        "delivery_fee": order.delivery_fee,
        "total": order.total,
        "support_email": settings.BREVO["SUPPORT_EMAIL"],
    }


def send_order_placed_vendor(order):
    try:
        return send_email(
            recipient=order.vendor.user.email,
            subject=f"New VendorHub order {order.order_code}",
            template="notifications/vendor_receive_order.html",
            context=_order_context(order),
        )
    except Exception:
        logger.exception("Order email failed for vendor on order %s", order.pk)
        return False


def send_order_placed_employee(order):
    try:
        return send_email(
            recipient=order.employee.user.email,
            subject=f"Order {order.order_code} confirmed",
            template="notifications/employee_comfirmed_order.html",
            context=_order_context(order),
        )
    except Exception:
        logger.exception("Order confirmation email failed for order %s", order.pk)
        return False


def send_order_ready_employee(order):
    try:
        return send_email(
            recipient=order.employee.user.email,
            subject=f"Order {order.order_code} is ready for collection",
            template="notifications/employee_ready_for_collections.html",
            context=_order_context(order),
        )
    except Exception:
        logger.exception("Order ready email failed for order %s", order.pk)
        return False
