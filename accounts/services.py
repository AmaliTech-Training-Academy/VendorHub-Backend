from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.models import AppUser, VendorProfile, EmployeeProfile


@transaction.atomic
def vendor_register(*, email: str, password: str, business_name: str, owner_name: str) -> AppUser:
    if AppUser.objects.filter(email=email).exists():
        raise ValidationError("A user with this email already exists.")

    validate_password(password)

    user = AppUser.objects.create_user(email=email, password=password, role="VENDOR")
    VendorProfile.objects.create(user=user, business_name=business_name, owner_name=owner_name)
    return user


@transaction.atomic
def employee_register(*, email: str, password: str, full_name: str) -> AppUser:
    if AppUser.objects.filter(email=email).exists():
        raise ValidationError("A user with this email already exists.")

    validate_password(password)

    user = AppUser.objects.create_user(email=email, password=password, role="EMPLOYEE")
    EmployeeProfile.objects.create(user=user, full_name=full_name)
    return user


def user_login(*, email: str, password: str) -> AppUser:
    user = authenticate(username=email, password=password)
    if user is None:
        raise ValidationError("Invalid email or password.")
    return user