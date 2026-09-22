from django.urls import path
from .apis import ProductDetailApi, ProductListCreateApi

urlpatterns = [
    path(
        "",
        ProductListCreateApi.as_view(),
    ),
    path(
        "<int:product_id>/",
        ProductDetailApi.as_view(),
    ),
]
