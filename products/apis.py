from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .pagination import ProductPagination
from .permissions import IsVendor
from .selectors import products_get, products_get_all
from .serializers import ProductSerializer
from .services import (
    get_owned_product,
    product_create,
    product_delete,
    product_update,
)


class ProductListCreateApi(GenericAPIView):
    permission_classes = [IsAuthenticated, IsVendor]
    pagination_class = ProductPagination

    def get(self, request, vendor_id):
        page = self.paginate_queryset(products_get(vendor_id=vendor_id))
        serializer = ProductSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    def post(self, request, vendor_id):
        serializer = ProductSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = product_create(
            vendor_id=vendor_id,
            user=request.user,
            **serializer.validated_data,
        )

        return Response(
            ProductSerializer(product).data,
            status=status.HTTP_201_CREATED,
        )


class ProductStorefrontApi(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        products = products_get_all()
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)


class ProductDetailApi(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def _get_owned_product(self, request, vendor_id, product_id):
        return get_owned_product(
            user=request.user,
            vendor_id=vendor_id,
            product_id=product_id,
        )

    def patch(self, request, vendor_id, product_id):
        product = self._get_owned_product(request, vendor_id, product_id)
        if product is None:
            return Response(
                {"message": "Product not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ProductSerializer(
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

        return Response(ProductSerializer(product).data)

    def delete(self, request, vendor_id, product_id):
        product = self._get_owned_product(request, vendor_id, product_id)
        if product is None:
            return Response(
                {"message": "Product not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        product_delete(product=product, user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)