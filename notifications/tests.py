from unittest.mock import patch

from django.conf import settings
from django.test import TestCase

from accounts.models import VendorProfile
from accounts.services import vendor_register
from notifications.services import (
    send_vendor_approved,
    send_vendor_declined,
)


class VendorEmailTests(TestCase):
    @patch("notifications.services.send_email", return_value=True)
    def test_vendor_registration_sends_pending_email_after_commit(self, send_email):
        with self.captureOnCommitCallbacks(execute=True):
            vendor_register(
                email="vendor@example.com",
                password="StrongPass123!",
                business_name="Test Shop",
                owner_name="Test Owner",
            )

        send_email.assert_called_once_with(
            recipient="vendor@example.com",
            subject="Your VendorHub account is pending verification",
            template="notifications/vendor_pending.html",
            context={
                "vendor_name": "Test Owner",
                "business_name": "Test Shop",
                "support_email": settings.BREVO["SUPPORT_EMAIL"],
            },
        )

    @patch("notifications.services.send_email", return_value=True)
    def test_approved_email_uses_vendor_details(self, send_email):
        vendor = self._create_vendor()

        self.assertTrue(send_vendor_approved(vendor))
        send_email.assert_called_once_with(
            recipient="vendor@example.com",
            subject="Your VendorHub account has been approved",
            template="notifications/vendor_approved.html",
            context={
                "vendor_name": "Test Owner",
                "business_name": "Test Shop",
                "support_email": settings.BREVO["SUPPORT_EMAIL"],
            },
        )

    @patch("notifications.services.send_email", return_value=True)
    def test_declined_email_includes_reason(self, send_email):
        vendor = self._create_vendor()
        vendor.decline_reason = "Please provide a registration certificate."

        self.assertTrue(send_vendor_declined(vendor))
        self.assertEqual(
            send_email.call_args.kwargs["context"]["reason"],
            "Please provide a registration certificate.",
        )

    @patch("notifications.services.send_vendor_approved", return_value=True)
    def test_approval_status_change_sends_email_automatically(self, send_approved):
        vendor = self._create_vendor()

        with self.captureOnCommitCallbacks(execute=True):
            vendor.verification_status = VendorProfile.VerificationStatus.APPROVED
            vendor.is_active = True
            vendor.save(update_fields=["verification_status", "is_active", "updated_at"])

        send_approved.assert_called_once_with(vendor)

    @staticmethod
    def _create_vendor():
        user = vendor_register(
            email="vendor@example.com",
            password="StrongPass123!",
            business_name="Test Shop",
            owner_name="Test Owner",
        )
        return VendorProfile.objects.get(user=user)
