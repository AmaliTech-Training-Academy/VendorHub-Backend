from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from accounts.models import AppUser, VendorProfile


class VendorStorefrontTests(APITestCase):
    def setUp(self):
        self.active_user = AppUser.objects.create_user(email="active@vendor.com", password="password123", role="VENDOR")
        self.active_vendor = VendorProfile.objects.create(
            user=self.active_user,
            business_name="Mama's Kitchen",
            delivery_fee="10.00",
            is_active=True
        )

        self.inactive_user = AppUser.objects.create_user(email="inactive@vendor.com", password="password123",
                                                         role="VENDOR")
        self.inactive_vendor = VendorProfile.objects.create(
            user=self.inactive_user,
            business_name="Closed Shop",
            delivery_fee="5.00",
            is_active=False
        )

        self.url = reverse('vendor-list')

    def test_get_active_vendors_only(self):
        # Authenticate the request since authentication is required
        self.client.force_authenticate(user=self.active_user)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['business_name'], "Mama's Kitchen")
        self.assertEqual(response.data[0]['delivery_fee'], "10.00")