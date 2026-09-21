from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from .models import Product
from .selectors import products_get
from .serializers import ProductSerializer
from .services import (
    product_create,
    product_delete,
    product_update,
)


@api_view(["GET", "POST"])
def products(request, vendor_id):
    vendor = getattr(request.user, "vendor_profile", None)

    if request.method == "GET":
        products = products_get(vendor_id=vendor_id)
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)

    if request.method == "POST":
        if vendor is None or vendor.id != vendor_id:
            raise PermissionDenied(
                "You can only create products for your own vendor account."
            )

        serializer = ProductSerializer(data=request.data)

        if serializer.is_valid():
            product = product_create(
                vendor_id=vendor_id,
                user=request.user,
                **serializer.validated_data,
            )

            return Response(
                ProductSerializer(product).data,
                status=201,
            )

        return Response(serializer.errors, status=400)


@api_view(["PATCH", "DELETE"])
def product_detail(request, vendor_id, product_id):
    vendor = getattr(request.user, "vendor_profile", None)

    if vendor is None or vendor.id != vendor_id:
        raise PermissionDenied(
            "You can only modify your own products."
        )

    product = Product.objects.filter(
        id=product_id,
        vendor_id=vendor_id,
        deleted_at__isnull=True,
    ).first()

    if product is None:
        return Response({"message": "Product not found."}, status=404)

    if request.method == "PATCH":
        serializer = ProductSerializer(
            product,
            data=request.data,
            partial=True,
        )

        if serializer.is_valid():
            product = product_update(
                product=product,
                user=request.user,
                **serializer.validated_data,
            )

            return Response(ProductSerializer(product).data)

        return Response(serializer.errors, status=400)

    if request.method == "DELETE":
        product_delete(
            product=product,
            user=request.user,
        )

        return Response(
            status=204,
        )