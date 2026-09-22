from django.urls import path
from .views import products, product_detail

urlpatterns = [
    path("vendors/<int:vendor_id>/products/", products),
    path(
        "vendors/<int:vendor_id>/products/<int:product_id>/",
        product_detail,
    ),
]