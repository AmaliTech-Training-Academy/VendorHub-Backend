from rest_framework.decorators import api_view
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
def products(request):
    vendor = request.user.vendor_profile

    if request.method == "GET":
        products = products_get(vendor_id=vendor.id)
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)

    if request.method == "POST":
        serializer = ProductSerializer(data=request.data)

        if serializer.is_valid():
            product = product_create(
                vendor_id=vendor.id,
                user=request.user,
                **serializer.validated_data,
            )

            return Response(
                ProductSerializer(product).data,
                status=201,
            )

        return Response(serializer.errors, status=400)


@api_view(["PATCH", "DELETE"])
def product_detail(request, product_id):
    vendor = request.user.vendor_profile

    product = Product.objects.get(
        id=product_id,
        vendor_id=vendor.id,
    )

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
            {"message": "Product deleted successfully."},
            status=200,
        )