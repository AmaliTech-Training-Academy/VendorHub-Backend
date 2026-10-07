import logging

import requests
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


class ResendEmailError(Exception):
    pass


def _from_address():
    config = settings.RESEND
    sender_name = config.get("SENDER_NAME", "VendorHub")
    sender_email = config.get("SENDER_EMAIL", "")
    return f"{sender_name} <{sender_email}>" if sender_name else sender_email


def send_email(*, recipient, subject, template, context):
    config = settings.RESEND
    if not config.get("API_KEY") or not config.get("SENDER_EMAIL"):
        logger.warning("Resend email skipped because it is not configured")
        return False

    html = render_to_string(template, context)
    payload = {
        "from": _from_address(),
        "to": [recipient],
        "subject": subject,
        "html": html,
        "text": strip_tags(html),
    }
    if config.get("REPLY_TO"):
        payload["reply_to"] = [config["REPLY_TO"]]

    try:
        response = requests.post(
            f'{config["API_URL"].rstrip("/")}/emails',
            json=payload,
            headers={"Authorization": f'Bearer {config["API_KEY"]}'},
            timeout=(3, 10),
        )
        if not response.ok:
            logger.warning(
                "Resend rejected email (HTTP %s): %s",
                response.status_code,
                response.text[:500],
            )
            return False
        data = response.json()
    except (requests.RequestException, ValueError):
        logger.exception("Resend email delivery failed for %s", recipient)
        return False

    if not data.get("id"):
        logger.error("Resend returned a response without an email id")
        return False
    return True


def _vendor_context(vendor):
    return {
        "vendor_name": vendor.owner_name,
        "business_name": vendor.business_name,
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
