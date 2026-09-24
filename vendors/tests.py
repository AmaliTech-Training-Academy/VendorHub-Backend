import datetime

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import AppUser, VendorProfile
from products.models import Product

from .models import DeliveryWindow
from .selectors import vendor_product_list
from .services import delivery_settings_update


class VendorStorefrontTests(APITestCase):
    def setUp(self):
        self.active_user = AppUser.objects.create_user(
            email="active@vendor.com",
            password="StrongPass123!",
            role="VENDOR",
        )
        self.active_vendor = VendorProfile.objects.create(
            user=self.active_user,
            business_name="Mama's Kitchen",
            owner_name="Mama",
            delivery_fee="10.00",
        )

        self.inactive_user = AppUser.objects.create_user(
            email="inactive@vendor.com",
            password="StrongPass123!",
            role="VENDOR",
        )
        self.inactive_vendor = VendorProfile.objects.create(
            user=self.inactive_user,
            business_name="Closed Shop",
            owner_name="Closed Owner",
            delivery_fee="5.00",
            is_active=False,
        )

        self.list_url = reverse("vendors:vendor-list")

    def get_products(self, vendor_id, **params):
        return self.client.get(reverse("vendors:vendor-product-list"), {"vendor_id": vendor_id, **params})

    def test_list_returns_active_vendors_only(self):
        self.client.force_authenticate(user=self.active_user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["business_name"], "Mama's Kitchen")
        self.assertEqual(response.data["results"][0]["delivery_fee"], "10.00")

    def test_vendor_with_disabled_account_is_hidden(self):
        # Shop switched on, but the owner's login is disabled: employees must not be able to order from them.
        self.active_user.is_active = False
        self.active_user.save(update_fields=["is_active"])
        Product.objects.create(vendor=self.active_vendor, name="Jollof", price="20.00")
        employee = AppUser.objects.create_user(email="employee@vendor.com", password="StrongPass123!", role="EMPLOYEE")
        self.client.force_authenticate(user=employee)

        list_response = self.client.get(self.list_url)
        products_response = self.get_products(self.active_vendor.id)

        self.assertEqual(list_response.data["count"], 0)
        self.assertEqual(products_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_available_products_never_include_closed_vendors(self):
        Product.objects.create(vendor=self.inactive_vendor, name="Closed shop dish", price="20.00")
        self.active_user.is_active = False
        self.active_user.save(update_fields=["is_active"])
        Product.objects.create(vendor=self.active_vendor, name="Disabled account dish", price="20.00")

        self.assertFalse(vendor_product_list(vendor_id=self.inactive_vendor.id).exists())
        self.assertFalse(vendor_product_list(vendor_id=self.active_vendor.id).exists())

    def test_list_does_not_expose_owner_personal_details(self):
        self.client.force_authenticate(user=self.active_user)

        vendor = self.client.get(self.list_url).data["results"][0]

        self.assertNotIn("owner_name", vendor)
        self.assertNotIn("is_active", vendor)

    def test_list_shows_category_summary_of_available_products(self):
        Product.objects.create(vendor=self.active_vendor, name="Sobolo", price="5.00", category="Drinks")
        Product.objects.create(vendor=self.active_vendor, name="Jollof", price="20.00", category="Local Dishes")
        Product.objects.create(vendor=self.active_vendor, name="Asaana", price="5.00", category="Drinks")
        Product.objects.create(vendor=self.active_vendor, name="Plain", price="5.00", category=None)
        Product.objects.create(vendor=self.active_vendor, name="Blank", price="5.00", category="  ")
        Product.objects.create(
            vendor=self.active_vendor, name="Sold Out", price="5.00", category="Snacks", in_stock=False
        )
        Product.objects.create(
            vendor=self.active_vendor, name="Removed", price="5.00", category="Desserts", deleted_at=timezone.now()
        )
        self.client.force_authenticate(user=self.active_user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.data["results"][0]["categories"], ["Drinks", "Local Dishes"])

    def test_vendor_without_products_has_empty_category_summary(self):
        self.client.force_authenticate(user=self.active_user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.data["results"][0]["categories"], [])

    def test_products_are_paginated(self):
        for i in range(3):
            Product.objects.create(vendor=self.active_vendor, name=f"Dish {i}", price="20.00")
        self.client.force_authenticate(user=self.active_user)

        response = self.get_products(self.active_vendor.id, page_size=2)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIsNotNone(response.data["next"])

    def test_list_requires_authentication(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_products_returns_in_stock_products_only(self):
        Product.objects.create(vendor=self.active_vendor, name="Jollof", price="20.00")
        Product.objects.create(vendor=self.active_vendor, name="Sold Out", price="20.00", in_stock=False)
        Product.objects.create(vendor=self.active_vendor, name="Removed", price="20.00", deleted_at=timezone.now())
        self.client.force_authenticate(user=self.active_user)

        response = self.get_products(self.active_vendor.id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "Jollof")

    def test_products_of_inactive_vendor_not_found(self):
        Product.objects.create(vendor=self.inactive_vendor, name="Hidden", price="20.00")
        self.client.force_authenticate(user=self.active_user)

        response = self.get_products(self.inactive_vendor.id)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data, {"detail": "Vendor not found."})

    def test_products_of_missing_vendor_not_found(self):
        self.client.force_authenticate(user=self.active_user)

        response = self.get_products(9999)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data, {"detail": "Vendor not found."})

    def test_products_requires_authentication(self):
        response = self.get_products(self.active_vendor.id)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_products_url_has_no_vendor_id_in_path(self):
        self.assertEqual(reverse("vendors:vendor-product-list"), "/api/vendors/products/")

    def test_old_products_url_with_vendor_id_no_longer_exists(self):
        # Typed on purpose: this URL must stay removed, so there is no route name to reverse.
        self.client.force_authenticate(user=self.active_user)

        response = self.client.get(f"/api/vendors/{self.active_vendor.id}/products/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_products_rejects_missing_or_invalid_vendor_id(self):
        self.client.force_authenticate(user=self.active_user)
        url = reverse("vendors:vendor-product-list")

        for params in ({}, {"vendor_id": "abc"}, {"vendor_id": "0"}, {"vendor_id": "-3"}):
            with self.subTest(params=params):
                response = self.client.get(url, params)

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("vendor_id", response.data)


class MyDeliverySettingsTests(APITestCase):
    def setUp(self):
        self.vendor_user = AppUser.objects.create_user(
            email="vendor@delivery.com",
            password="StrongPass123!",
            role="VENDOR",
        )
        self.vendor = VendorProfile.objects.create(
            user=self.vendor_user,
            business_name="Mama's Kitchen",
            owner_name="Mama",
            delivery_fee="10.00",
        )

        self.other_vendor_user = AppUser.objects.create_user(
            email="other@delivery.com",
            password="StrongPass123!",
            role="VENDOR",
        )
        self.other_vendor = VendorProfile.objects.create(
            user=self.other_vendor_user,
            business_name="Other Shop",
            owner_name="Other",
            delivery_fee="3.00",
        )

        self.employee_user = AppUser.objects.create_user(
            email="employee@delivery.com",
            password="StrongPass123!",
            role="EMPLOYEE",
        )

        self.url = reverse("vendors:my-delivery-settings")
        self.list_url = reverse("vendors:vendor-list")

    def window(self, name, start, end, **extra):
        return {"window_name": name, "start_time": start, "end_time": end, **extra}

    def settings_data(self, **overrides):
        data = {
            "available_days": ["WEDNESDAY", "MONDAY"],
            "delivery_fee": "15.00",
            "time_windows": [
                self.window("Morning", "10:00", "12:00"),
                self.window("Afternoon", "14:00", "16:00"),
            ],
        }
        data.update(overrides)
        return data

    def save_settings(self, data=None, user=None):
        self.client.force_authenticate(user=user or self.vendor_user)
        return self.client.put(self.url, data or self.settings_data(), format="json")

    def storefront_vendor(self, vendor):
        self.client.force_authenticate(user=self.employee_user)
        results = self.client.get(self.list_url).data["results"]
        return next(v for v in results if v["id"] == vendor.id)

    # Security: a vendor can only ever read or change their own settings.

    def test_url_has_no_vendor_id(self):
        self.assertEqual(self.url, "/api/vendors/me/delivery-settings/")

    def test_old_url_with_vendor_id_no_longer_exists(self):
        # Typed on purpose: this URL must stay removed, so there is no route name to reverse.
        self.client.force_authenticate(user=self.other_vendor_user)

        response = self.client.put(
            f"/api/vendors/{self.vendor.id}/delivery-settings/", self.settings_data(), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.vendor.refresh_from_db()
        self.assertEqual(str(self.vendor.delivery_fee), "10.00")

    def test_each_vendor_only_changes_their_own_settings(self):
        response = self.save_settings(user=self.other_vendor_user)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.other_vendor.refresh_from_db()
        self.assertEqual(str(self.other_vendor.delivery_fee), "15.00")
        self.assertEqual(DeliveryWindow.objects.filter(vendor=self.other_vendor).count(), 2)
        self.vendor.refresh_from_db()
        self.assertEqual(str(self.vendor.delivery_fee), "10.00")
        self.assertFalse(DeliveryWindow.objects.filter(vendor=self.vendor).exists())

    def test_employee_cannot_read_or_change_settings(self):
        self.client.force_authenticate(user=self.employee_user)

        get_response = self.client.get(self.url)
        put_response = self.client.put(self.url, self.settings_data(), format="json")

        self.assertEqual(get_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(put_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(put_response.data, {"detail": "Only vendors can manage delivery settings."})
        self.assertFalse(DeliveryWindow.objects.exists())

    def test_inactive_vendor_cannot_read_or_change_settings(self):
        self.vendor.is_active = False
        self.vendor.save(update_fields=["is_active"])
        self.client.force_authenticate(user=self.vendor_user)

        get_response = self.client.get(self.url)
        put_response = self.client.put(self.url, self.settings_data(), format="json")

        self.assertEqual(get_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(put_response.status_code, status.HTTP_403_FORBIDDEN)
        self.vendor.refresh_from_db()
        self.assertEqual(str(self.vendor.delivery_fee), "10.00")
        self.assertFalse(DeliveryWindow.objects.exists())

    def test_cannot_update_another_vendors_window(self):
        foreign_window = DeliveryWindow.objects.create(
            vendor=self.other_vendor,
            window_name="Theirs",
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 0),
            available_days=["MONDAY"],
        )
        data = self.settings_data(time_windows=[self.window("Stolen", "10:00", "12:00", id=foreign_window.id)])

        response = self.save_settings(data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {"detail": f"Delivery window {foreign_window.id} does not belong to this vendor."},
        )
        foreign_window.refresh_from_db()
        self.assertEqual(foreign_window.window_name, "Theirs")
        self.vendor.refresh_from_db()
        self.assertEqual(str(self.vendor.delivery_fee), "10.00")

    def test_rejects_window_id_below_one(self):
        # Rejected by the serializer, so the error points at the id field instead of coming from the service.
        for window_id in (0, -3):
            with self.subTest(window_id=window_id):
                data = self.settings_data(time_windows=[self.window("Morning", "10:00", "12:00", id=window_id)])

                response = self.save_settings(data)

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("id", response.data["time_windows"][0])

        self.vendor.refresh_from_db()
        self.assertEqual(str(self.vendor.delivery_fee), "10.00")
        self.assertFalse(DeliveryWindow.objects.exists())

    def test_requires_authentication(self):
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            self.client.put(self.url, self.settings_data(), format="json").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    # Acceptance criterion 1: the vendor can set days, time windows and a flat delivery fee.

    def test_vendor_can_save_delivery_settings(self):
        response = self.save_settings()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["available_days"], ["MONDAY", "WEDNESDAY"])
        self.assertEqual(response.data["delivery_fee"], "15.00")
        morning, afternoon = response.data["time_windows"]
        self.assertEqual(
            dict(morning),
            {
                "id": morning["id"],
                "window_name": "Morning",
                "start_time": "10:00",
                "end_time": "12:00",
                "sort_order": 0,
            },
        )
        self.assertEqual(afternoon["window_name"], "Afternoon")
        self.assertEqual(afternoon["sort_order"], 1)

        self.vendor.refresh_from_db()
        self.assertEqual(str(self.vendor.delivery_fee), "15.00")
        windows = DeliveryWindow.objects.filter(vendor=self.vendor)
        self.assertEqual(windows.count(), 2)
        for window in windows:
            self.assertEqual(window.available_days, ["MONDAY", "WEDNESDAY"])

    def test_vendor_can_read_own_settings(self):
        self.save_settings()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["available_days"], ["MONDAY", "WEDNESDAY"])
        self.assertEqual(response.data["delivery_fee"], "15.00")
        self.assertEqual([w["window_name"] for w in response.data["time_windows"]], ["Morning", "Afternoon"])

    def test_vendor_without_settings_gets_empty_lists(self):
        self.client.force_authenticate(user=self.vendor_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"available_days": [], "delivery_fee": "10.00", "time_windows": []})

    def test_zero_fee_is_allowed(self):
        response = self.save_settings(self.settings_data(delivery_fee="0.00"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["delivery_fee"], "0.00")

    def test_duplicate_days_are_saved_once(self):
        response = self.save_settings(self.settings_data(available_days=["FRIDAY", "MONDAY", "FRIDAY"]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["available_days"], ["MONDAY", "FRIDAY"])

    def test_rejects_invalid_settings(self):
        invalid_cases = {
            "no time windows": self.settings_data(time_windows=[]),
            "missing time windows": {"available_days": ["MONDAY"], "delivery_fee": "15.00"},
            "missing fee": {"available_days": ["MONDAY"], "time_windows": [self.window("A", "10:00", "12:00")]},
            "negative fee": self.settings_data(delivery_fee="-1.00"),
            "no days": self.settings_data(available_days=[]),
            "missing days": {"delivery_fee": "15.00", "time_windows": [self.window("A", "10:00", "12:00")]},
            "invalid day": self.settings_data(available_days=["FUNDAY"]),
            "end before start": self.settings_data(time_windows=[self.window("Late", "12:00", "10:00")]),
            "end equals start": self.settings_data(time_windows=[self.window("Instant", "10:00", "10:00")]),
            "bad time format": self.settings_data(time_windows=[self.window("Bad", "10am", "12pm")]),
            "duplicate names": self.settings_data(
                time_windows=[self.window("Morning", "08:00", "09:00"), self.window("morning", "10:00", "11:00")]
            ),
            "overlapping windows": self.settings_data(
                time_windows=[self.window("A", "10:00", "12:00"), self.window("B", "11:00", "13:00")]
            ),
        }

        for case, data in invalid_cases.items():
            with self.subTest(case=case):
                response = self.save_settings(data)

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.vendor.refresh_from_db()
        self.assertEqual(str(self.vendor.delivery_fee), "10.00")
        self.assertFalse(DeliveryWindow.objects.exists())

    def test_back_to_back_windows_are_allowed(self):
        data = self.settings_data(
            time_windows=[self.window("Late morning", "10:00", "12:00"), self.window("Lunch", "12:00", "14:00")]
        )

        response = self.save_settings(data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_service_validates_windows_before_saving(self):
        # Like products, the service runs full_clean(), so bad data is rejected even if the API checks are bypassed.
        invalid_windows = {
            "end before start": {"window_name": "Late", "start_time": datetime.time(12), "end_time": datetime.time(10)},
            "name too long": {"window_name": "x" * 101, "start_time": datetime.time(10), "end_time": datetime.time(12)},
        }

        for case, window in invalid_windows.items():
            with self.subTest(case=case):
                with self.assertRaises(ValidationError):
                    delivery_settings_update(
                        user=self.vendor_user,
                        delivery_fee="15.00",
                        available_days=["MONDAY"],
                        time_windows=[window],
                    )

                self.vendor.refresh_from_db()
                self.assertEqual(str(self.vendor.delivery_fee), "10.00")
                self.assertFalse(DeliveryWindow.objects.exists())

    def test_service_validates_fee_before_saving(self):
        window = {"window_name": "Morning", "start_time": datetime.time(10), "end_time": datetime.time(12)}

        for fee in ("-5.00", "-0.01", "abc", "12.345", "123456789.00", None):
            with self.subTest(fee=fee):
                with self.assertRaises(ValidationError):
                    delivery_settings_update(
                        user=self.vendor_user,
                        delivery_fee=fee,
                        available_days=["MONDAY"],
                        time_windows=[window],
                    )

                self.vendor.refresh_from_db()
                self.assertEqual(str(self.vendor.delivery_fee), "10.00")
                self.assertFalse(DeliveryWindow.objects.exists())

    def test_service_accepts_zero_fee(self):
        window = {"window_name": "Morning", "start_time": datetime.time(10), "end_time": datetime.time(12)}

        delivery_settings_update(
            user=self.vendor_user,
            delivery_fee="0",
            available_days=["MONDAY"],
            time_windows=[window],
        )

        self.vendor.refresh_from_db()
        self.assertEqual(str(self.vendor.delivery_fee), "0.00")

    def test_database_rejects_window_ending_before_it_starts(self):
        with self.assertRaises(IntegrityError):
            DeliveryWindow.objects.create(
                vendor=self.vendor,
                window_name="Broken",
                start_time=datetime.time(12, 0),
                end_time=datetime.time(10, 0),
            )

    # Acceptance criterion 2: settings are saved and shown on the employee-facing storefront.

    def test_storefront_shows_delivery_settings(self):
        self.save_settings()

        vendor = self.storefront_vendor(self.vendor)

        self.assertEqual(vendor["available_days"], ["MONDAY", "WEDNESDAY"])
        self.assertEqual(vendor["delivery_fee"], "15.00")
        self.assertEqual([w["window_name"] for w in vendor["delivery_windows"]], ["Morning", "Afternoon"])

    def test_storefront_does_not_query_per_vendor(self):
        self.save_settings()
        self.client.force_authenticate(user=self.employee_user)
        with CaptureQueriesContext(connection) as two_vendors:
            self.client.get(self.list_url)

        for i in range(5):
            user = AppUser.objects.create_user(email=f"extra{i}@delivery.com", password="StrongPass123!", role="VENDOR")
            extra = VendorProfile.objects.create(user=user, business_name=f"Extra {i}", owner_name="Extra")
            DeliveryWindow.objects.create(
                vendor=extra,
                window_name="Morning",
                start_time=datetime.time(9, 0),
                end_time=datetime.time(10, 0),
                available_days=["MONDAY"],
            )
            Product.objects.create(vendor=extra, name=f"Dish {i}", price="10.00", category=f"Category {i}")
        with CaptureQueriesContext(connection) as seven_vendors:
            self.client.get(self.list_url)

        self.assertEqual(len(seven_vendors), len(two_vendors))

    # Acceptance criterion 3: the vendor can update settings at any time; changes appear immediately.

    def test_update_replaces_settings_and_appears_immediately(self):
        first = self.save_settings().data
        morning_id = first["time_windows"][0]["id"]
        afternoon_id = first["time_windows"][1]["id"]

        data = {
            "available_days": ["FRIDAY"],
            "delivery_fee": "20.00",
            "time_windows": [
                self.window("Evening", "18:00", "20:00"),
                self.window("Early morning", "08:00", "10:00", id=morning_id),
            ],
        }
        response = self.save_settings(data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        vendor = self.storefront_vendor(self.vendor)
        self.assertEqual(vendor["available_days"], ["FRIDAY"])
        self.assertEqual(vendor["delivery_fee"], "20.00")
        self.assertEqual([w["window_name"] for w in vendor["delivery_windows"]], ["Evening", "Early morning"])

        # The existing window was updated in place; the dropped one was deactivated, not deleted.
        morning = DeliveryWindow.objects.get(id=morning_id)
        self.assertEqual(morning.window_name, "Early morning")
        self.assertEqual(morning.available_days, ["FRIDAY"])
        self.assertTrue(morning.is_active)
        self.assertFalse(DeliveryWindow.objects.get(id=afternoon_id).is_active)
        self.assertEqual(DeliveryWindow.objects.filter(vendor=self.vendor).count(), 3)

