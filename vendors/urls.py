from django.urls import path

from .apis import VendorListApi, VendorProductListApi

app_name = "vendors"

urlpatterns = [
    path("", VendorListApi.as_view(), name="vendor-list"),
    path("<int:vendor_id>/products/", VendorProductListApi.as_view(), name="vendor-product-list"),
]
