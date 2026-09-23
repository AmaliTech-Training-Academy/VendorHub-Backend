from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import AppUser, VendorProfile, EmployeeProfile
from accounts.services import vendor_register, employee_register, user_login
from django.core.exceptions import ValidationError

class VendorRegistrationTests(TestCase):
    def test_vendor_register_creates_user_and_profile(self):
        user = vendor_register(
            email="v@test.com", password="pass12345",
            business_name="Test Biz", owner_name="Test Owner"
        )
        self.assertEqual(user.role, "VENDOR")
        self.assertTrue(VendorProfile.objects.filter(user=user).exists())

    def test_vendor_register_hashes_password(self):
        user = vendor_register(
            email="v2@test.com", password="pass12345",
            business_name="Test Biz", owner_name="Test Owner"
        )
        self.assertNotEqual(user.password, "pass12345")
        self.assertTrue(user.check_password("pass12345"))

    def test_vendor_register_duplicate_email_fails(self):
        vendor_register(email="dup@test.com", password="pass12345",
                         business_name="A", owner_name="B")
        with self.assertRaises(ValidationError):
            vendor_register(email="dup@test.com", password="pass12345",
                             business_name="C", owner_name="D")


class EmployeeRegistrationTests(TestCase):
    def test_employee_register_creates_user_and_profile(self):
        user = employee_register(email="e@test.com", password="pass12345", full_name="Emp Name")
        self.assertEqual(user.role, "EMPLOYEE")
        self.assertTrue(EmployeeProfile.objects.filter(user=user).exists())


class LoginTests(TestCase):
    def setUp(self):
        self.user = vendor_register(
            email="login@test.com", password="pass12345",
            business_name="Biz", owner_name="Owner"
        )

    def test_login_success(self):
        user = user_login(email="login@test.com", password="pass12345")
        self.assertEqual(user.id, self.user.id)

    def test_login_wrong_password_fails(self):
        with self.assertRaises(ValidationError):
            user_login(email="login@test.com", password="wrongpass")

    def test_login_nonexistent_email_fails(self):
        with self.assertRaises(ValidationError):
            user_login(email="nobody@test.com", password="pass12345")

class VendorRegistrationEdgeCaseTests(APITestCase):
    """Edge cases for vendor registration via the API."""

    def setUp(self):
        self.url = reverse("accounts:vendor-register")

    def test_vendor_register_rejects_short_password(self):
        response = self.client.post(self.url, {
            "email": "vendor_short@test.com",
            "password": "abc",
            "business_name": "TechCorp",
            "owner_name": "Owner",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_vendor_register_rejects_common_password(self):
        response = self.client.post(self.url, {
            "email": "vendor_common@test.com",
            "password": "password",
            "business_name": "TechCorp",
            "owner_name": "Owner",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_vendor_register_rejects_numeric_password(self):
        response = self.client.post(self.url, {
            "email": "vendor_num@test.com",
            "password": "12345678",
            "business_name": "TechCorp",
            "owner_name": "Owner",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_vendor_register_rejects_oversized_business_name(self):
        response = self.client.post(self.url, {
            "email": "vendor_long@test.com",
            "password": "StrongPass123!",
            "business_name": "a" * 256,
            "owner_name": "Owner",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_vendor_register_rejects_oversized_owner_name(self):
        response = self.client.post(self.url, {
            "email": "vendor_longowner@test.com",
            "password": "StrongPass123!",
            "business_name": "TechCorp",
            "owner_name": "b" * 256,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_vendor_register_rejects_invalid_email(self):
        response = self.client.post(self.url, {
            "email": "not-an-email",
            "password": "StrongPass123!",
            "business_name": "TechCorp",
            "owner_name": "Owner",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class EmployeeRegistrationEdgeCaseTests(APITestCase):
    """Edge cases for employee registration via the API."""

    def setUp(self):
        self.url = reverse("accounts:employee-register")

    def test_employee_register_rejects_short_password(self):
        response = self.client.post(self.url, {
            "email": "emp_short@test.com",
            "password": "abc",
            "full_name": "Test User",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_employee_register_rejects_oversized_full_name(self):
        response = self.client.post(self.url, {
            "email": "emp_long@test.com",
            "password": "StrongPass123!",
            "full_name": "c" * 256,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_employee_register_rejects_duplicate_email(self):
        AppUser.objects.create_user(
            email="emp_dup@test.com", password="StrongPass123!", role="EMPLOYEE"
        )
        response = self.client.post(self.url, {
            "email": "emp_dup@test.com",
            "password": "StrongPass123!",
            "full_name": "Test",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LoginEdgeCaseTests(APITestCase):
    """Edge cases for login via the API."""

    def setUp(self):
        self.url = reverse("accounts:login")
        self.user = AppUser.objects.create_user(
            email="login_edge@test.com",
            password="StrongPass123!",
            role="EMPLOYEE",
        )

    def test_login_fails_for_inactive_user(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post(self.url, {
            "email": "login_edge@test.com",
            "password": "StrongPass123!",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_returns_user_metadata(self):
        response = self.client.post(self.url, {
            "email": "login_edge@test.com",
            "password": "StrongPass123!",
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "login_edge@test.com")
        self.assertEqual(response.data["role"], "EMPLOYEE")
        self.assertIn("id", response.data)

    def test_login_rejects_invalid_email_format(self):
        response = self.client.post(self.url, {
            "email": "not-an-email",
            "password": "StrongPass123!",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class PasswordSecurityTests(APITestCase):

    def setUp(self):
        self.register_url = reverse("accounts:vendor-register")
        self.login_url = reverse("accounts:login")

    def test_password_is_hashed_in_database(self):
        self.client.post(self.register_url, {
            "email": "hash_check@test.com",
            "password": "StrongPass123!",
            "business_name": "HashShop",
            "owner_name": "Hash Owner",
        })
        user = AppUser.objects.get(email="hash_check@test.com")

        self.assertNotEqual(user.password, "StrongPass123!")

        self.assertTrue(
            user.password.startswith("pbkdf2_sha256$"),
            f"Expected hashed password, got: {user.password[:30]}"
        )

        self.assertTrue(user.check_password("StrongPass123!"))

    def test_login_wrong_password_returns_generic_error(self):
        AppUser.objects.create_user(
            email="generic@test.com", password="StrongPass123!", role="EMPLOYEE",
        )
        response = self.client.post(self.login_url, {
            "email": "generic@test.com",
            "password": "WrongPassword999!",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response_text = str(response.data).lower()
        self.assertIn("invalid email or password", response_text)
        self.assertNotIn("wrong password", response_text)
        self.assertNotIn("incorrect password", response_text)
        self.assertNotIn("user not found", response_text)
        self.assertNotIn("email not found", response_text)
        self.assertNotIn("email does not exist", response_text)

    def test_login_unknown_email_returns_same_generic_error(self):
        r1 = self.client.post(self.login_url, {
            "email": "ghost@test.com",
            "password": "StrongPass123!",
        })

        AppUser.objects.create_user(
            email="real@test.com", password="StrongPass123!", role="EMPLOYEE",
        )
        r2 = self.client.post(self.login_url, {
            "email": "real@test.com",
            "password": "WrongPassword999!",
        })

        self.assertEqual(r1.status_code, r2.status_code)
        self.assertEqual(r1.data, r2.data)