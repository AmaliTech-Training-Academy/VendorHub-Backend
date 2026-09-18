from django.urls import path
from .views import products, product_detail

urlpatterns = [
    path("products/", products),
    path("products/<int:product_id>/", product_detail),
]