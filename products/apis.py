from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Product
from .pagination import ProductPagination
from .permissions import IsVendor
from .selectors import products_get
from .services import (
    get_owned_product,
    get_vendor_for_user,
    product_create,
    product_delete,
    product_update,
)


class ProductListCreateApi(GenericAPIView):
    permission_classes = [IsAuthenticated, IsVendor]
    pagination_class = ProductPagination

    class InputSerializer(serializers.ModelSerializer):
        class Meta:
            model = Product
            fields = [
                "name",
                "price",
                "description",
                "category",
                "in_stock",
            ]

        def validate_price(self, value):
            if value <= 0:
                raise serializers.ValidationError(
                    "Price must be greater than 0."
                )

            return value

    class OutputSerializer(serializers.ModelSerializer):
        class Meta:
            model = Product
            fields = [
                "id",
                "vendor",
                "name",
                "price",
                "description",
                "category",
                "in_stock",
                "created_at",
                "updated_at",
                "deleted_at",
            ]
            read_only_fields = fields

    def get(self, request):
        vendor = get_vendor_for_user(request.user)
        page = self.paginate_queryset(products_get(vendor_id=vendor.id))
        serializer = self.OutputSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = product_create(
            user=request.user,
            **serializer.validated_data,
        )

        return Response(
            self.OutputSerializer(product).data,
            status=status.HTTP_201_CREATED,
        )


class ProductDetailApi(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    class InputSerializer(ProductListCreateApi.InputSerializer):
        pass

    class OutputSerializer(ProductListCreateApi.OutputSerializer):
        pass

    def _get_owned_product(self, request, product_id):
        return get_owned_product(
            user=request.user,
            product_id=product_id,
        )

    def patch(self, request, product_id):
        product = self._get_owned_product(request, product_id)
        if product is None:
            return Response(
                {"message": "Product not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = self.InputSerializer(
            product,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        product = product_update(
            product=product,
            user=request.user,
            **serializer.validated_data,
        )

        return Response(self.OutputSerializer(product).data)

    def delete(self, request, product_id):
        product = self._get_owned_product(request, product_id)
        if product is None:
            return Response(
                {"message": "Product not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        product_delete(product=product, user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)