from rest_framework import generics
from drf_spectacular.utils import extend_schema
from accounts.models import VendorProfile
from .serializers import VendorStorefrontSerializer

@extend_schema(
    summary="List Active Vendors",
    description="Retrieves a public list of all active vendor storefronts (filtering where is_active=True).",
    tags=["Vendor Storefront"]
)
class VendorListView(generics.ListAPIView):
    serializer_class = VendorStorefrontSerializer

    def get_queryset(self):
        return VendorProfile.objects.filter(is_active=True)