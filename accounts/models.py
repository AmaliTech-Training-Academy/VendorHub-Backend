from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models

# Create your models here.

class AppUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)

class AppUser(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ('VENDOR', 'Vendor'),
        ('EMPLOYEE', 'Employee'),
    )
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    password = models.CharField(max_length=255, db_column='password_hash')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AppUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

class EmployeeProfile(models.Model):
    user = models.OneToOneField(AppUser, on_delete=models.CASCADE, related_name='employee_profile')
    full_name = models.CharField(max_length=255)
    office_address = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=16, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name

class VendorProfile(models.Model):
    class VerificationStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        DECLINED = 'DECLINED', 'Declined'

    user = models.OneToOneField(AppUser, on_delete=models.CASCADE, related_name='vendor_profile')
    business_name = models.CharField(max_length=255)
    owner_name = models.CharField(max_length=255)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    verification_status = models.CharField(
        max_length=10,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
    )
    decline_reason = models.CharField(max_length=255, blank=True, default='')
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.business_name