from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import AppUser, VendorProfile
from products.models import Product


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

    def product_list_url(self, vendor_id):
        return reverse("vendors:vendor-product-list", args=[vendor_id])

    def test_list_returns_active_vendors_only(self):
        self.client.force_authenticate(user=self.active_user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["business_name"], "Mama's Kitchen")
        self.assertEqual(response.data["results"][0]["delivery_fee"], "10.00")

    def test_products_are_paginated(self):
        for i in range(3):
            Product.objects.create(vendor=self.active_vendor, name=f"Dish {i}", price="20.00")
        self.client.force_authenticate(user=self.active_user)

        response = self.client.get(self.product_list_url(self.active_vendor.id), {"page_size": 2})

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

        response = self.client.get(self.product_list_url(self.active_vendor.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "Jollof")

    def test_products_of_inactive_vendor_not_found(self):
        Product.objects.create(vendor=self.inactive_vendor, name="Hidden", price="20.00")
        self.client.force_authenticate(user=self.active_user)

        response = self.client.get(self.product_list_url(self.inactive_vendor.id))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data, {"detail": "Vendor not found."})

    def test_products_of_missing_vendor_not_found(self):
        self.client.force_authenticate(user=self.active_user)

        response = self.client.get(self.product_list_url(9999))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_products_requires_authentication(self):
        response = self.client.get(self.product_list_url(self.active_vendor.id))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
