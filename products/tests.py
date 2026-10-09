import io
import os
import shutil
import tempfile
from unittest import mock

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import AppUser, VendorProfile

from .models import Product
from .apis import ProductListCreateApi


def make_image(name="product.png", size=(10, 10), noise=False):
    if noise:
        image = Image.frombytes("RGB", size, os.urandom(size[0] * size[1] * 3))
    else:
        image = Image.new("RGB", size, "red")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class ProductInputSerializerTests(TestCase):
    def test_rejects_non_positive_price_with_clear_message(self):
        for price in ("0", "-1"):
            with self.subTest(price=price):
                serializer = ProductListCreateApi.InputSerializer(
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
        self.collection_url = "/api/products/"

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

    def test_other_vendor_cannot_access_another_vendors_product(self):
        product = self.create_product()
        self.authenticate_as(self.other_vendor_user)

        response = self.client.patch(
            f"/api/products/products/{product.id}/",
            {"name": "Hacked"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        product.refresh_from_db()
        self.assertEqual(product.name, "Coffee")

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
        self.assertEqual(list_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_product_price_constraint_rejects_direct_invalid_write(self):
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            Product.objects.create(
                vendor=self.vendor,
                **self.product_data(price="0"),
            )


class ProductImageTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_root = tempfile.mkdtemp()
        cls.media_override = override_settings(
            MEDIA_ROOT=cls.media_root,
            STORAGES={
                **settings.STORAGES,
                "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            },
        )
        cls.media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.media_override.disable()
        shutil.rmtree(cls.media_root, ignore_errors=True)
        super().tearDownClass()

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
        self.client.force_authenticate(user=self.vendor_user)
        self.collection_url = "/api/products/"

    def create_product(self, **extra):
        data = {"name": "Coffee", "price": "12.50", **extra}
        return self.client.post(self.collection_url, data, format="multipart")

    def product_with_image(self):
        response = self.create_product(image=make_image())
        return Product.objects.get(id=response.data["id"])

    def detail_url(self, product):
        return f"{self.collection_url}{product.id}/"

    def test_vendor_can_create_product_with_image(self):
        response = self.create_product(image=make_image())

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        image = Product.objects.get(id=response.data["id"]).image
        self.assertTrue(image.name.startswith(f"products/{self.vendor.id}/"))
        self.assertTrue(image.name.endswith(".png"))
        self.assertTrue(os.path.exists(image.path))
        self.assertEqual(response.data["image"], f"http://testserver/media/{image.name}")

    def test_product_without_image_returns_null(self):
        response = self.client.post(
            self.collection_url,
            {"name": "Coffee", "price": "12.50"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.data["image"])

    def test_list_includes_image_url(self):
        product = self.product_with_image()

        response = self.client.get(self.collection_url)

        self.assertEqual(
            response.data["results"][0]["image"],
            f"http://testserver/media/{product.image.name}",
        )

    def test_replacing_image_deletes_old_file(self):
        product = self.product_with_image()
        old_path = product.image.path

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(
                self.detail_url(product),
                {"image": make_image("new.png")},
                format="multipart",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        product.refresh_from_db()
        self.assertFalse(os.path.exists(old_path))
        self.assertTrue(os.path.exists(product.image.path))

    def test_vendor_can_remove_image(self):
        product = self.product_with_image()
        old_path = product.image.path

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(self.detail_url(product), {"image": None}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["image"])
        self.assertFalse(os.path.exists(old_path))

    def test_price_update_keeps_image(self):
        product = self.product_with_image()

        response = self.client.patch(self.detail_url(product), {"price": "15.00"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["image"], f"http://testserver/media/{product.image.name}")

    def test_rejects_file_that_is_not_an_image(self):
        fake = SimpleUploadedFile("product.png", b"not really an image", content_type="image/png")

        response = self.create_product(image=fake)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Product.objects.exists())

    def test_rejects_image_over_size_limit(self):
        response = self.create_product(image=make_image(size=(1000, 1000), noise=True))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(str(response.data["image"][0]), "Image must be 2 MB or smaller.")
        self.assertFalse(Product.objects.exists())

    def test_price_update_works_when_saved_image_cannot_be_read(self):
        product = self.product_with_image()

        with mock.patch.object(FileSystemStorage, "size", side_effect=FileNotFoundError):
            response = self.client.patch(self.detail_url(product), {"price": "15.00"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        product.refresh_from_db()
        self.assertEqual(str(product.price), "15.00")

    def test_failed_old_image_cleanup_still_returns_success(self):
        product = self.product_with_image()

        with (
            mock.patch.object(FileSystemStorage, "delete", side_effect=OSError("storage down")),
            self.assertLogs("products.services", level="ERROR") as logs,
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.client.patch(self.detail_url(product), {"image": None}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        product.refresh_from_db()
        self.assertFalse(product.image)
        self.assertIn("Could not delete old product image", logs.output[0])
