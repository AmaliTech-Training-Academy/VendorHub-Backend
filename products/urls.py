from django.urls import path
from .apis import ProductDetailApi, ProductListCreateApi

urlpatterns = [
    path(
        "vendors/<int:vendor_id>/products/",
        ProductListCreateApi.as_view(),
    ),
    path(
        "vendors/<int:vendor_id>/products/<int:product_id>/",
        ProductDetailApi.as_view(),
    ),
]