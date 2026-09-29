from datetime import timedelta, time
from decimal import Decimal
from unittest import mock

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import AppUser, EmployeeProfile, VendorProfile
from orders.models import Order, OrderItem
from orders.services import order_create
from products.models import Product
from vendors.models import DeliveryWindow
from rest_framework import status


class OrderCreateApiTests(APITestCase):

    def setUp(self):
        self.vendor_user = AppUser.objects.create_user(
            email="vendor@example.com",
            password="pass12345",
            role="VENDOR",
        )

        self.vendor = VendorProfile.objects.create(
            user=self.vendor_user,
            business_name="Vendor A",
            owner_name="Vendor Owner",
            delivery_fee=Decimal("5.00"),
        )

        self.other_vendor_user = AppUser.objects.create_user(
            email="other-vendor@example.com",
            password="pass12345",
            role="VENDOR",
        )

        self.other_vendor = VendorProfile.objects.create(
            user=self.other_vendor_user,
            business_name="Vendor B",
            owner_name="Other Owner",
            delivery_fee=Decimal("10.00"),
        )

        self.employee_user = AppUser.objects.create_user(
            email="employee@example.com",
            password="pass12345",
            role="EMPLOYEE",
        )

        EmployeeProfile.objects.create(
            user=self.employee_user,
            full_name="Employee One",
        )

        self.window = DeliveryWindow.objects.create(
            vendor=self.vendor,
            window_name="Lunch",
            start_time="12:00",
            end_time="13:00",
            available_days=["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"],
        )

        self.other_window = DeliveryWindow.objects.create(
            vendor=self.other_vendor,
            window_name="Dinner",
            start_time="18:00",
            end_time="19:00",
            available_days=["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"],
        )

        self.product = Product.objects.create(
            vendor=self.vendor,
            name="Rice",
            price=Decimal("10.00"),
            in_stock=True,
        )

        self.second_product = Product.objects.create(
            vendor=self.vendor,
            name="Water",
            price=Decimal("2.50"),
            in_stock=True,
        )

        self.other_product = Product.objects.create(
            vendor=self.other_vendor,
            name="Other Vendor Rice",
            price=Decimal("20.00"),
            in_stock=True,
        )

        self.url = reverse("orders:order-create")

        self.delivery_date = timezone.localdate() + timedelta(days=1)

        # Make sure the default delivery date is an allowed weekday.
        while (
            self.delivery_date.strftime("%A").upper()
            not in self.window.available_days
        ):
            self.delivery_date += timedelta(days=1)

        self.payload = {
            "vendor_id": self.vendor.id,
            "items": [
                {
                    "product_id": self.product.id,
                    "quantity": 2,
                },
                {
                    "product_id": self.second_product.id,
                    "quantity": 1,
                },
            ],
            "selected_delivery_window": self.window.id,
            "delivery_date": self.delivery_date.isoformat(),
        }

        # Orders require authentication.
        self.client.force_authenticate(
            user=self.employee_user,
        )

    def test_valid_order_returns_201_and_calculates_amounts(self):
        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        order = Order.objects.get(
            id=response.data["id"],
        )

        self.assertEqual(
            order.vendor_id,
            self.vendor.id,
        )

        self.assertEqual(
            order.employee_id,
            self.employee_user.employee_profile.id,
        )

        self.assertEqual(
            order.delivery_date,
            self.delivery_date,
        )

        self.assertEqual(
            order.order_items.count(),
            2,
        )

        self.assertEqual(
            order.subtotal,
            Decimal("22.50"),
        )

        self.assertEqual(
            order.delivery_fee,
            Decimal("5.00"),
        )

        self.assertEqual(
            order.total,
            Decimal("27.50"),
        )

        self.assertEqual(
            len(response.data["items"]),
            2,
        )

    def test_vendor_cannot_place_employee_order(self):
        self.client.force_authenticate(
            user=self.vendor_user,
        )

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 403)

        self.assertEqual(
            Order.objects.count(),
            0,
        )

    def test_inactive_vendor_is_rejected(self):
        self.vendor.is_active = False
        self.vendor.save(
            update_fields=["is_active"],
        )

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)

        self.assertEqual(
            Order.objects.count(),
            0,
        )

    def test_out_of_stock_product_is_rejected(self):
        self.product.in_stock = False
        self.product.save(
            update_fields=["in_stock"],
        )

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)

        self.assertIn(
            "out of stock",
            response.data["detail"],
        )

        self.assertEqual(
            Order.objects.count(),
            0,
        )

    def test_deleted_product_is_rejected(self):
        self.product.deleted_at = timezone.now()
        self.product.save(
            update_fields=["deleted_at"],
        )

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)

        self.assertIn(
            "deleted",
            response.data["detail"],
        )

        self.assertEqual(
            Order.objects.count(),
            0,
        )

    def test_product_from_another_vendor_is_rejected(self):
        payload = {
            **self.payload,
            "items": [
                {
                    "product_id": self.other_product.id,
                    "quantity": 1,
                }
            ],
        }

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)

        self.assertIn(
            "another vendor",
            response.data["detail"],
        )

        self.assertEqual(
            Order.objects.count(),
            0,
        )

    def test_duplicate_products_are_rejected(self):
        payload = {
            **self.payload,
            "items": [
                {
                    "product_id": self.product.id,
                    "quantity": 1,
                },
                {
                    "product_id": self.product.id,
                    "quantity": 2,
                },
            ],
        }

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)

        self.assertIn(
            "Duplicate products",
            str(response.data),
        )

        self.assertEqual(
            Order.objects.count(),
            0,
        )

    def test_invalid_quantity_is_rejected(self):
        payload = {
            **self.payload,
            "items": [
                {
                    "product_id": self.product.id,
                    "quantity": 0,
                }
            ],
        }

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)

        self.assertEqual(
            Order.objects.count(),
            0,
        )

    def test_empty_items_are_rejected(self):
        payload = {
            **self.payload,
            "items": [],
        }

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)

        self.assertEqual(
            Order.objects.count(),
            0,
        )

    def test_invalid_delivery_window_is_rejected(self):
        payload = {
            **self.payload,
            "selected_delivery_window": 999999,
        }

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)

        self.assertIn(
            "Delivery window",
            response.data["detail"],
        )

        self.assertEqual(
            Order.objects.count(),
            0,
        )

    def test_inactive_delivery_window_is_rejected(self):
        self.window.is_active = False
        self.window.save(
            update_fields=["is_active"],
        )

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)

        self.assertIn(
            "Delivery window",
            response.data["detail"],
        )

        self.assertEqual(
            Order.objects.count(),
            0,
        )

    def test_delivery_window_from_another_vendor_is_rejected(self):
        payload = {
            **self.payload,
            "selected_delivery_window": self.other_window.id,
        }

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)

        self.assertIn(
            "does not belong",
            response.data["detail"],
        )

        self.assertEqual(
            Order.objects.count(),
            0,
        )

    def test_client_cannot_manipulate_calculated_prices(self):
        payload = {
            **self.payload,
            "subtotal": "999.99",
            "delivery_fee": "0.00",
            "total_amount": "1.00",
        }

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        self.assertEqual(
            response.data["subtotal"],
            "22.50",
        )

        self.assertEqual(
            response.data["delivery_fee"],
            "5.00",
        )

        self.assertEqual(
            response.data["total_amount"],
            "27.50",
        )

    def test_item_creation_failure_rolls_back_order(self):
        with mock.patch.object(
            OrderItem.objects,
            "bulk_create",
            side_effect=Exception("forced item failure"),
        ):
            with self.assertRaises(Exception):
                order_create(
                    user=self.employee_user,
                    **self.payload,
                )

        self.assertEqual(
            Order.objects.count(),
            0,
        )

        self.assertEqual(
            OrderItem.objects.count(),
            0,
        )

    def test_past_delivery_date_is_rejected(self):
        payload = {
            **self.payload,
            "delivery_date": (
                timezone.localdate() - timedelta(days=1)
            ).isoformat(),
        }

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)

        self.assertIn(
            "past",
            response.data["detail"],
        )

        self.assertEqual(
            Order.objects.count(),
            0,
        )

    def test_delivery_date_on_unavailable_day_is_rejected(self):
        unavailable_date = timezone.localdate() + timedelta(days=1)

        allowed_days = set(self.window.available_days)

        while unavailable_date.strftime("%A").upper() in allowed_days:
            unavailable_date += timedelta(days=1)

        payload = {
            **self.payload,
            "delivery_date": unavailable_date.isoformat(),
        }

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)

        self.assertIn(
            "not available",
            response.data["detail"],
        )

        self.assertEqual(
            Order.objects.count(),
            0,
        )

    def test_delivery_window_already_started_today_is_rejected(self):
        today = timezone.localdate()
        today_name = today.strftime("%A").upper()

        self.window.start_time = time(0, 0)
        self.window.end_time = time(23, 59)
        self.window.available_days = [today_name]
        self.window.save()

        payload = {
            **self.payload,
            "delivery_date": today.isoformat(),
            "selected_delivery_window": self.window.id,
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already started", response.data["detail"])



class OrderStatusUpdateTests(APITestCase):

    def setUp(self):
        # Vendor A - owner of the order
        self.vendor_a_user = AppUser.objects.create_user(
            email="vendor_a_status@test.com",
            password="pass12345",
            role="VENDOR",
        )
        self.vendor_a = VendorProfile.objects.create(
            user=self.vendor_a_user,
            business_name="Vendor A",
            owner_name="Owner A",
            delivery_fee=Decimal("5.00"),
        )

        # Vendor B - tries to update Vendor A's order
        self.vendor_b_user = AppUser.objects.create_user(
            email="vendor_b_status@test.com",
            password="pass12345",
            role="VENDOR",
        )
        self.vendor_b = VendorProfile.objects.create(
            user=self.vendor_b_user,
            business_name="Vendor B",
            owner_name="Owner B",
            delivery_fee=Decimal("5.00"),
        )

        # Employee - the order's customer
        self.employee_user = AppUser.objects.create_user(
            email="employee_status@test.com",
            password="pass12345",
            role="EMPLOYEE",
        )
        self.employee = EmployeeProfile.objects.create(
            user=self.employee_user,
            full_name="Employee One",
        )

        # Delivery window for the order
        self.window = DeliveryWindow.objects.create(
            vendor=self.vendor_a,
            window_name="Lunch",
            start_time="12:00",
            end_time="13:00",
            available_days=["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"],
        )

        # The order under test - owned by Vendor A
        self.order = Order.objects.create(
            employee=self.employee,
            vendor=self.vendor_a,
            delivery_window=self.window,
            delivery_date=timezone.localdate() + timedelta(days=1),
            order_code="VH-TEST-STATUS-001",
            selected_window_name="Lunch",
            selected_start_time="12:00",
            selected_end_time="13:00",
            subtotal=Decimal("20.00"),
            delivery_fee=Decimal("5.00"),
            total=Decimal("25.00"),
            status=Order.Status.RECEIVED,
        )

        self.url = reverse(
            "orders:order-status-update",
            kwargs={"order_id": self.order.id},
        )

    def test_requires_authentication(self):
        response = self.client.patch(
            self.url,
            {"status": "PREPARING"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_owner_can_update_status_to_preparing(self):
        self.client.force_authenticate(user=self.vendor_a_user)

        response = self.client.patch(
            self.url,
            {"status": "PREPARING"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "PREPARING")

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "PREPARING")

    def test_owner_can_update_to_ready_for_collection(self):
        self.client.force_authenticate(user=self.vendor_a_user)

        response = self.client.patch(
            self.url,
            {"status": "READY FOR COLLECTION"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "READY FOR COLLECTION")

    def test_invalid_status_is_rejected(self):
        self.client.force_authenticate(user=self.vendor_a_user)

        response = self.client.patch(
            self.url,
            {"status": "DONE"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.RECEIVED)

    def test_other_vendor_cannot_update_order(self):
        """IDOR-safe: Vendor B cannot update Vendor A's order."""
        self.client.force_authenticate(user=self.vendor_b_user)

        response = self.client.patch(
            self.url,
            {"status": "PREPARING"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.RECEIVED)

    def test_nonexistent_order_returns_400(self):
        self.client.force_authenticate(user=self.vendor_a_user)

        url = reverse(
            "orders:order-status-update",
            kwargs={"order_id": 999999},
        )

        response = self.client.patch(
            url,
            {"status": "PREPARING"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not found", response.data["detail"])