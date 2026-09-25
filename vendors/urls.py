from django.urls import path

from .apis import MyDeliverySettingsApi, VendorListApi, VendorProductListApi

app_name = "vendors"

urlpatterns = [
    path("", VendorListApi.as_view(), name="vendor-list"),
    path("me/delivery-settings/", MyDeliverySettingsApi.as_view(), name="my-delivery-settings"),
    path("products/", VendorProductListApi.as_view(), name="vendor-product-list"),
]
