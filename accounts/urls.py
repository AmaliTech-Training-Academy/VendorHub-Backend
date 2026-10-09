from django.urls import path

from accounts.apis import (
    CurrentUserApi,
    EmployeeRegisterApi,
    LoginApi,
    VendorRegisterApi,
)

app_name = "accounts"

urlpatterns = [
    path("vendor/register/", VendorRegisterApi.as_view(), name="vendor-register"),
    path("employee/register/", EmployeeRegisterApi.as_view(), name="employee-register"),
    path("me/", CurrentUserApi.as_view(), name="current-user"),
    path("login/", LoginApi.as_view(), name="login"),
]