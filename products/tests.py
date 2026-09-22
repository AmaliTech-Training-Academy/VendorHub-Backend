from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import AppUser, VendorProfile

from .models import Product
from .serializers import ProductSerializer


class ProductSerializerTests(TestCase):
    def test_rejects_non_positive_price_with_clear_message(self):
        for price in ("0", "-1"):
            with self.subTest(price=price):
                serializer = ProductSerializer(
                    data={"name": "Coffee", "price": price}
                )

                self.assertFalse(serializer.is_valid())
                self.assertEqual(
                    str(serializer.errors["price"][0]),
                    "Price must be greater than 0.",
                )


class ProductApiTests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.vendor_user = AppUser.objects.create_user(
			email="vendor@example.com",
			password="StrongPass123!",
			role="VENDOR",
		)
		self.vendor = VendorProfile.objects.create(
			user=self.vendor_user,
			business_name="Demo Store",
			owner_name="Demo Owner",
		)
		self.other_vendor_user = AppUser.objects.create_user(
			email="other-vendor@example.com",
			password="StrongPass123!",
			role="VENDOR",
		)
		self.other_vendor = VendorProfile.objects.create(
			user=self.other_vendor_user,
			business_name="Other Store",
			owner_name="Other Owner",
		)
		self.employee_user = AppUser.objects.create_user(
			email="employee@example.com",
			password="StrongPass123!",
			role="EMPLOYEE",
		)
		self.collection_url = f"/api/vendors/{self.vendor.id}/products/"

	def product_data(self, **overrides):
		data = {
			"name": "Coffee",
			"description": "Whole bean coffee",
			"price": "12.50",
			"category": "Beverages",
			"in_stock": True,
		}
		data.update(overrides)
		return data

	def authenticate_as(self, user):
		self.client.force_authenticate(user=user)

	def create_product(self):
		return Product.objects.create(
			vendor=self.vendor,
			**self.product_data(),
		)

	def test_owner_can_create_and_receive_paginated_products(self):
		self.authenticate_as(self.vendor_user)

		response = self.client.post(
			self.collection_url,
			self.product_data(),
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data["name"], "Coffee")

		list_response = self.client.get(self.collection_url)

		self.assertEqual(list_response.status_code, status.HTTP_200_OK)
		self.assertEqual(list_response.data["count"], 1)
		self.assertEqual(list_response.data["results"][0]["price"], "12.50")

	def test_employee_and_anonymous_users_cannot_access_vendor_endpoint(self):
		self.authenticate_as(self.employee_user)
		employee_response = self.client.get(self.collection_url)
		self.assertEqual(employee_response.status_code, status.HTTP_403_FORBIDDEN)

		self.client.force_authenticate(user=None)
		anonymous_response = self.client.get(self.collection_url)
		self.assertEqual(anonymous_response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_employee_storefront_lists_only_active_products(self):
		active_product = self.create_product()
		deleted_product = Product.objects.create(
			vendor=self.vendor,
			**self.product_data(name="Deleted"),
		)
		deleted_product.deleted_at = deleted_product.created_at
		deleted_product.save(update_fields=["deleted_at"])

		inactive_vendor = VendorProfile.objects.create(
			user=AppUser.objects.create_user(
				email="inactive-vendor@example.com",
				password="StrongPass123!",
				role="VENDOR",
			),
			business_name="Inactive Store",
			owner_name="Inactive Owner",
			is_active=False,
		)
		Product.objects.create(
			vendor=inactive_vendor,
			**self.product_data(name="Inactive"),
		)

		self.authenticate_as(self.employee_user)
		response = self.client.get("/api/products/")

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data["count"], 1)
		self.assertEqual(
			[item["id"] for item in response.data["results"]],
			[active_product.id],
		)

		self.client.force_authenticate(user=None)
		anonymous_response = self.client.get("/api/products/")
		self.assertEqual(
			anonymous_response.status_code,
			status.HTTP_401_UNAUTHORIZED,
		)

	def test_other_vendor_cannot_create_for_this_vendor(self):
		self.authenticate_as(self.other_vendor_user)

		response = self.client.post(
			self.collection_url,
			self.product_data(),
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
		self.assertFalse(Product.objects.filter(vendor=self.vendor).exists())

	def test_owner_can_update_and_delete_product(self):
		product = self.create_product()
		self.authenticate_as(self.vendor_user)
		detail_url = f"{self.collection_url}{product.id}/"

		update_response = self.client.patch(
			detail_url,
			{"price": "15.00", "in_stock": False},
			format="json",
		)
		self.assertEqual(update_response.status_code, status.HTTP_200_OK)
		self.assertEqual(update_response.data["price"], "15.00")

		delete_response = self.client.delete(detail_url)
		self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
		self.assertEqual(self.client.get(self.collection_url).data["count"], 0)

	def test_missing_product_returns_not_found(self):
		self.authenticate_as(self.vendor_user)

		response = self.client.patch(
			f"{self.collection_url}999/",
			{"name": "Missing"},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

	def test_inactive_vendor_cannot_manage_or_list_products(self):
		self.vendor.is_active = False
		self.vendor.save(update_fields=["is_active"])
		self.authenticate_as(self.vendor_user)

		create_response = self.client.post(
			self.collection_url,
			self.product_data(),
			format="json",
		)
		self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)

		list_response = self.client.get(self.collection_url)
		self.assertEqual(list_response.status_code, status.HTTP_200_OK)
		self.assertEqual(list_response.data["count"], 0)

	def test_product_price_constraint_rejects_direct_invalid_write(self):
		from django.db import IntegrityError

		with self.assertRaises(IntegrityError):
			Product.objects.create(
				vendor=self.vendor,
				**self.product_data(price="0"),
			)
