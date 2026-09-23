from rest_framework import generics
from drf_spectacular.utils import extend_schema
from accounts.models import VendorProfile
from products.models import Product
from .serializers import VendorStorefrontSerializer, ProductSerializer

@extend_schema(summary="List Active Vendors", tags=["Vendor Storefront"])
class VendorListView(generics.ListAPIView):
    serializer_class = VendorStorefrontSerializer

    def get_queryset(self):
        return VendorProfile.objects.filter(is_active=True)


@extend_schema(summary="List Vendor's In-Stock Products", tags=["Vendor Storefront"])
class VendorProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer

    def get_queryset(self):
        vendor_id = self.kwargs.get("pk")
        return Product.objects.filter(
            vendor_id=vendor_id,
            in_stock=True,
            deleted_at__isnull=True
        )