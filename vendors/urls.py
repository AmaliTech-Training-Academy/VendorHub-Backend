from django.urls import path
from .views import VendorListView, VendorProductListView

urlpatterns = [
    path('', VendorListView.as_view(), name='vendor-list'),
    path('<int:pk>/products/', VendorProductListView.as_view(), name='vendor-product-list'),
]

