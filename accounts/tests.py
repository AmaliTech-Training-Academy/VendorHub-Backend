from django.test import TestCase
from accounts.models import AppUser, VendorProfile, EmployeeProfile
from accounts.services import vendor_register, employee_register, user_login
from django.core.exceptions import ValidationError

# Create your tests here.

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