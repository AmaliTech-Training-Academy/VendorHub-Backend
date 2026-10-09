from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import AppUser, EmployeeProfile, VendorProfile
from orders.models import Order, OrderItem
from orders.services import order_create
from products.models import Product
from vendors.models import DeliveryWindow


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
            verification_status=VendorProfile.VerificationStatus.APPROVED,
            is_active=True,
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
            verification_status=VendorProfile.VerificationStatus.APPROVED,
            is_active=True,
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
            available_days=[
                "MONDAY",
                "TUESDAY",
                "WEDNESDAY",
                "THURSDAY",
                "FRIDAY",
            ],
        )

        self.other_window = DeliveryWindow.objects.create(
            vendor=self.other_vendor,
            window_name="Dinner",
            start_time="18:00",
            end_time="19:00",
            available_days=[
                "MONDAY",
                "TUESDAY",
                "WEDNESDAY",
                "THURSDAY",
                "FRIDAY",
            ],
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
        self.list_url = reverse("orders:order-list")

        self.delivery_date = timezone.localdate() + timedelta(days=1)

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

        self.client.force_authenticate(user=self.employee_user)

    def test_employee_can_create_order(self):
        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        order = Order.objects.get(id=response.data["id"])

        self.assertEqual(order.employee.user, self.employee_user)
        self.assertEqual(order.vendor, self.vendor)
        self.assertEqual(order.subtotal, Decimal("22.50"))
        self.assertEqual(order.delivery_fee, Decimal("5.00"))
        self.assertEqual(order.total, Decimal("27.50"))
        self.assertEqual(order.status, Order.Status.RECEIVED)
        self.assertEqual(order.order_items.count(), 2)

    @mock.patch("notifications.services.send_order_placed_employee")
    @mock.patch("notifications.services.send_order_placed_vendor")
    def test_order_creation_sends_vendor_and_employee_emails(
        self,
        send_vendor_email,
        send_employee_email,
    ):
        with self.captureOnCommitCallbacks(execute=True):
            order = order_create(
                user=self.employee_user,
                vendor_id=self.vendor.id,
                items=self.payload["items"],
                selected_delivery_window=self.window.id,
                delivery_date=self.delivery_date,
            )

        send_vendor_email.assert_called_once_with(order)
        send_employee_email.assert_called_once_with(order)

    def test_vendor_cannot_create_employee_order(self):
        self.client.force_authenticate(user=self.vendor_user)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_inactive_vendor_cannot_receive_order(self):
        self.vendor.is_active = False
        self.vendor.save(update_fields=["is_active"])

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_out_of_stock_product_cannot_be_ordered(self):
        self.product.in_stock = False
        self.product.save(update_fields=["in_stock"])

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_deleted_product_cannot_be_ordered(self):
        self.product.deleted_at = timezone.now()
        self.product.save(update_fields=["deleted_at"])

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_product_from_another_vendor_cannot_be_ordered(self):
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

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
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

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
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

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
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

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
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

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_inactive_delivery_window_is_rejected(self):
        self.window.is_active = False
        self.window.save(update_fields=["is_active"])

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
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

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_client_cannot_manipulate_calculated_prices(self):
        payload = {
            **self.payload,
            "subtotal": "1.00",
            "delivery_fee": "0.00",
            "total": "1.00",
            "total_amount": "1.00",
        }

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        order = Order.objects.get(id=response.data["id"])

        self.assertEqual(order.subtotal, Decimal("22.50"))
        self.assertEqual(order.delivery_fee, Decimal("5.00"))
        self.assertEqual(order.total, Decimal("27.50"))

    def test_transaction_rolls_back_when_order_creation_fails(self):
        initial_order_count = Order.objects.count()
        initial_item_count = OrderItem.objects.count()

        with mock.patch(
            "orders.services.OrderItem.objects.bulk_create",
            side_effect=RuntimeError("Simulated failure"),
        ), self.assertRaises(RuntimeError):
            order_create(
                user=self.employee_user,
                vendor_id=self.vendor.id,
                items=[
                    {
                        "product_id": self.product.id,
                        "quantity": 1,
                    }
                ],
                selected_delivery_window=self.window.id,
                delivery_date=self.delivery_date,
            )

        self.assertEqual(
            Order.objects.count(),
            initial_order_count,
        )
        self.assertEqual(
            OrderItem.objects.count(),
            initial_item_count,
        )

    def test_past_delivery_date_is_rejected(self):
        past_date = timezone.localdate() - timedelta(days=1)

        payload = {
            **self.payload,
            "delivery_date": past_date.isoformat(),
        }

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_delivery_date_on_unavailable_day_is_rejected(self):
        unavailable_date = self.delivery_date

        for _ in range(7):
            unavailable_date += timedelta(days=1)

            if (
                unavailable_date.strftime("%A").upper()
                not in self.window.available_days
            ):
                break

        payload = {
            **self.payload,
            "delivery_date": unavailable_date.isoformat(),
        }

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_delivery_window_already_started_today_is_rejected(self):
        now = timezone.localtime()

        started_window = DeliveryWindow.objects.create(
            vendor=self.vendor,
            window_name="Started Window",
            start_time=(now - timedelta(minutes=30)).time(),
            end_time=(now + timedelta(minutes=30)).time(),
            available_days=[
                "MONDAY",
                "TUESDAY",
                "WEDNESDAY",
                "THURSDAY",
                "FRIDAY",
                "SATURDAY",
                "SUNDAY",
            ],
        )

        payload = {
            **self.payload,
            "selected_delivery_window": started_window.id,
            "delivery_date": timezone.localdate().isoformat(),
        }

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    # ------------------------------------------------------------------
    # GET ORDER LIST TESTS
    # ------------------------------------------------------------------

    def test_employee_can_get_own_orders(self):
        payload = {
            **self.payload,
            "delivery_date": self.delivery_date,
        }

        order = order_create(
            user=self.employee_user,
            **payload,
        )

        response = self.client.get(
            self.list_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            len(response.data),
            1,
        )
        self.assertEqual(
            response.data[0]["id"],
            order.id,
        )

    def test_employee_only_gets_own_orders(self):
        other_employee_user = AppUser.objects.create_user(
            email="other-employee@example.com",
            password="pass12345",
            role="EMPLOYEE",
        )

        EmployeeProfile.objects.create(
            user=other_employee_user,
            full_name="Employee Two",
        )

        payload = {
            **self.payload,
            "delivery_date": self.delivery_date,
        }

        own_order = order_create(
            user=self.employee_user,
            **payload,
        )

        other_order = order_create(
            user=other_employee_user,
            **payload,
        )

        response = self.client.get(
            self.list_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        returned_order_ids = {
            item["id"]
            for item in response.data
        }

        self.assertIn(
            own_order.id,
            returned_order_ids,
        )
        self.assertNotIn(
            other_order.id,
            returned_order_ids,
        )

    def test_vendor_can_get_orders_for_their_vendor(self):
        payload = {
            **self.payload,
            "delivery_date": self.delivery_date,
        }

        order = order_create(
            user=self.employee_user,
            **payload,
        )

        self.client.force_authenticate(
            user=self.vendor_user,
        )

        response = self.client.get(
            self.list_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            len(response.data),
            1,
        )
        self.assertEqual(
            response.data[0]["id"],
            order.id,
        )

    def test_vendor_only_gets_their_own_orders(self):
        other_employee_user = AppUser.objects.create_user(
            email="other-employee@example.com",
            password="pass12345",
            role="EMPLOYEE",
        )

        EmployeeProfile.objects.create(
            user=other_employee_user,
            full_name="Employee Two",
        )

        payload = {
            **self.payload,
            "delivery_date": self.delivery_date,
        }

        own_order = order_create(
            user=self.employee_user,
            **payload,
        )

        other_vendor_payload = {
            "vendor_id": self.other_vendor.id,
            "items": [
                {
                    "product_id": self.other_product.id,
                    "quantity": 1,
                }
            ],
            "selected_delivery_window": self.other_window.id,
            "delivery_date": self.delivery_date,
        }

        other_order = order_create(
            user=other_employee_user,
            **other_vendor_payload,
        )

        self.client.force_authenticate(
            user=self.vendor_user,
        )

        response = self.client.get(
            self.list_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        returned_order_ids = {
            item["id"]
            for item in response.data
        }

        self.assertIn(
            own_order.id,
            returned_order_ids,
        )
        self.assertNotIn(
            other_order.id,
            returned_order_ids,
        )

    def test_unauthenticated_user_cannot_get_orders(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(
            self.list_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


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
            verification_status=VendorProfile.VerificationStatus.APPROVED,
            is_active=True,
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
            verification_status=VendorProfile.VerificationStatus.APPROVED,
            is_active=True,
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
            available_days=[
                "MONDAY",
                "TUESDAY",
                "WEDNESDAY",
                "THURSDAY",
                "FRIDAY",
            ],
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

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_owner_can_update_status_to_preparing(self):
        self.client.force_authenticate(
            user=self.vendor_a_user,
        )

        response = self.client.patch(
            self.url,
            {"status": "PREPARING"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data["status"],
            "PREPARING",
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            "PREPARING",
        )

    def test_owner_can_update_to_ready_for_collection(self):
        self.client.force_authenticate(
            user=self.vendor_a_user,
        )

        with (
            mock.patch("notifications.services.send_order_ready_employee") as send_email,
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.client.patch(
                self.url,
                {"status": "READY FOR COLLECTION"},
                format="json",
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data["status"],
            "READY FOR COLLECTION",
        )
        send_email.assert_called_once()

    def test_invalid_status_is_rejected(self):
        self.client.force_authenticate(
            user=self.vendor_a_user,
        )

        response = self.client.patch(
            self.url,
            {"status": "DONE"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            Order.Status.RECEIVED,
        )

    def test_other_vendor_cannot_update_order(self):
        """IDOR-safe: Vendor B cannot update Vendor A's order."""
        self.client.force_authenticate(
            user=self.vendor_b_user,
        )

        response = self.client.patch(
            self.url,
            {"status": "PREPARING"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            Order.Status.RECEIVED,
        )

    def test_nonexistent_order_returns_400(self):
        self.client.force_authenticate(
            user=self.vendor_a_user,
        )

        url = reverse(
            "orders:order-status-update",
            kwargs={"order_id": 999999},
        )

        response = self.client.patch(
            url,
            {"status": "PREPARING"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertIn(
            "not found",
            response.data["detail"].lower(),
        )