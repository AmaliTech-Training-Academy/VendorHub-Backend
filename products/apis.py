from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Product
from .selectors import products_get
from .serializers import ProductSerializer
from .services import product_create, product_delete, product_update


class ProductListCreateApi(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, vendor_id):
        products = products_get(vendor_id=vendor_id)
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)

    def post(self, request, vendor_id):
        vendor = getattr(request.user, "vendor_profile", None)
        if vendor is None or vendor.id != vendor_id:
            raise PermissionDenied(
                "You can only create products for your own vendor account."
            )

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


class ProductDetailApi(APIView):
    permission_classes = [IsAuthenticated]

    def _get_owned_product(self, request, vendor_id, product_id):
        vendor = getattr(request.user, "vendor_profile", None)
        if vendor is None or vendor.id != vendor_id:
            raise PermissionDenied(
                "You can only modify your own products."
            )

        return Product.objects.filter(
            id=product_id,
            vendor_id=vendor_id,
            deleted_at__isnull=True,
        ).first()

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