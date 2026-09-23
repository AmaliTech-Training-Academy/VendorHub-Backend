from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import VendorProfile
from products.models import Product

from .pagination import VendorPagination
from .selectors import vendor_get, vendor_list, vendor_product_list


class VendorListApi(GenericAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class = VendorPagination

    class OutputSerializer(serializers.ModelSerializer):
        class Meta:
            model = VendorProfile
            ref_name = "VendorStorefront"
            fields = [
                "id",
                "business_name",
                "owner_name",
                "delivery_fee",
                "is_active",
            ]
            read_only_fields = fields

    @extend_schema(
        summary="List Active Vendors",
        tags=["Vendor Storefront"],
        responses=OutputSerializer(many=True),
    )
    def get(self, request):
        page = self.paginate_queryset(vendor_list())
        serializer = self.OutputSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)


class VendorProductListApi(GenericAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class = VendorPagination

    class OutputSerializer(serializers.ModelSerializer):
        class Meta:
            model = Product
            ref_name = "VendorProduct"
            fields = [
                "id",
                "name",
                "description",
                "category",
                "price",
                "in_stock",
            ]
            read_only_fields = fields

    @extend_schema(
        summary="List Vendor's In-Stock Products",
        tags=["Vendor Storefront"],
        responses=OutputSerializer(many=True),
    )
    def get(self, request, vendor_id):
        vendor = vendor_get(vendor_id=vendor_id)
        if vendor is None:
            return Response(
                {"detail": "Vendor not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        page = self.paginate_queryset(vendor_product_list(vendor_id=vendor.id))
        serializer = self.OutputSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)
