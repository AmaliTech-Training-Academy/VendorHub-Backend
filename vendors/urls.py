from django.urls import path

from .apis import MyDeliverySettingsApi, MyStorefrontApi, VendorListApi, VendorProductListApi

app_name = "vendors"

urlpatterns = [
    path("", VendorListApi.as_view(), name="vendor-list"),
    path("me/delivery-settings/", MyDeliverySettingsApi.as_view(), name="my-delivery-settings"),
    path("me/storefront/", MyStorefrontApi.as_view(), name="my-storefront"),
    path("products/", VendorProductListApi.as_view(), name="vendor-product-list"),
]
