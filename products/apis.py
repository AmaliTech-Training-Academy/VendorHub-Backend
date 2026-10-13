from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
)
from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MAX_IMAGE_SIZE_MB, Product
from .pagination import ProductPagination
from .permissions import IsApprovedVendor
from .selectors import products_get
from .services import (
    get_owned_product,
    get_vendor_for_user,
    product_create,
    product_delete,
    product_update,
)


class ProductNotFoundSerializer(serializers.Serializer):
    """Shape of the 404 body returned when the product is missing or not owned by the vendor."""

    message = serializers.CharField()

    class Meta:
        ref_name = "ProductNotFound"


FORBIDDEN_RESPONSE = OpenApiResponse(
    description=(
        "The logged-in user is not an approved vendor. "
        'Body: `{"detail": "..."}`.'
    ),
)

VALIDATION_ERROR_RESPONSE = OpenApiResponse(
    response=OpenApiTypes.OBJECT,
    description=(
        "Validation failed. Field-level errors, "
        'e.g. `{"price": ["Price must be greater than 0."]}`.'
    ),
)


class ProductListCreateApi(GenericAPIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]
    pagination_class = ProductPagination

    class InputSerializer(serializers.ModelSerializer):
        class Meta:
            model = Product
            ref_name = "ProductInput"
            fields = [
                "name",
                "price",
                "description",
                "category",
                "image",
                "in_stock",
            ]
            extra_kwargs = {
                "image": {
                    "allow_null": True,
                    "help_text": (
                        f"Image file (PNG, JPG, GIF or WebP), max {MAX_IMAGE_SIZE_MB} MB. "
                        "Send null to remove the image."
                    ),
                },
                # Without an explicit default, multipart treats a missing boolean as an unchecked
                # checkbox (False), so products created with an image would be hidden from employees.
                "in_stock": {"default": True},
            }

        def validate_price(self, value):
            if value <= 0:
                raise serializers.ValidationError(
                    "Price must be greater than 0."
                )

            return value

    class OutputSerializer(serializers.ModelSerializer):
        class Meta:
            model = Product
            ref_name = "ProductOutput"
            fields = [
                "id",
                "vendor",
                "name",
                "price",
                "description",
                "category",
                "image",
                "in_stock",
                "created_at",
                "updated_at",
                "deleted_at",
            ]
            read_only_fields = fields

    @extend_schema(
        summary="List My Products",
        description=(
            "Returns a paginated list of the logged-in vendor's own products. "
            "Requires a valid access token and an approved vendor account."
        ),
        tags=["Products"],
        responses={
            200: OutputSerializer(many=True),
            403: FORBIDDEN_RESPONSE,
        },
    )
    def get(self, request):
        vendor = get_vendor_for_user(request.user)
        page = self.paginate_queryset(products_get(vendor_id=vendor.id))
        serializer = self.OutputSerializer(page, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)

    @extend_schema(
        summary="Create a Product",
        description=(
            "Adds a new product to the logged-in vendor's catalog. "
            "Requires a valid access token and an approved vendor account. "
            "Send as multipart/form-data when uploading an image; JSON works without one.\n\n"
            "- **price**: must be greater than 0.\n"
            "- **in_stock**: whether the product can currently be ordered."
        ),
        tags=["Products"],
        request={"multipart/form-data": InputSerializer, "application/json": InputSerializer},
        responses={
            201: OutputSerializer,
            400: VALIDATION_ERROR_RESPONSE,
            403: FORBIDDEN_RESPONSE,
        },
        examples=[
            OpenApiExample(
                "Create product request",
                value={
                    "name": "Jollof Rice Pack",
                    "price": "35.00",
                    "description": "Serves one, comes with chicken.",
                    "category": "Meals",
                    "in_stock": True,
                },
                request_only=True,
            ),
            OpenApiExample(
                "Invalid price",
                value={"price": ["Price must be greater than 0."]},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = product_create(
            user=request.user,
            **serializer.validated_data,
        )

        return Response(
            self.OutputSerializer(product, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class ProductDetailApi(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    class InputSerializer(ProductListCreateApi.InputSerializer):
        class Meta(ProductListCreateApi.InputSerializer.Meta):
            ref_name = "ProductUpdateInput"

    class OutputSerializer(ProductListCreateApi.OutputSerializer):
        class Meta(ProductListCreateApi.OutputSerializer.Meta):
            ref_name = "ProductDetailOutput"

    def _get_owned_product(self, request, product_id):
        return get_owned_product(
            user=request.user,
            product_id=product_id,
        )

    @extend_schema(
        summary="Update a Product",
        description=(
            "Partially updates one of the logged-in vendor's own products. "
            "Only the fields you send are changed. Returns 404 if the product "
            "does not exist or belongs to another vendor. "
            "Send as multipart/form-data when uploading an image; JSON works without one.\n\n"
            "- **price**: if sent, must be greater than 0."
        ),
        tags=["Products"],
        parameters=[
            OpenApiParameter(
                name="product_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description="ID of the product to update.",
            ),
        ],
        request={"multipart/form-data": InputSerializer, "application/json": InputSerializer},
        responses={
            200: OutputSerializer,
            400: VALIDATION_ERROR_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: ProductNotFoundSerializer,
        },
        examples=[
            OpenApiExample(
                "Update price and stock",
                value={"price": "40.00", "in_stock": False},
                request_only=True,
            ),
            OpenApiExample(
                "Product not found",
                value={"message": "Product not found."},
                response_only=True,
                status_codes=["404"],
            ),
        ],
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

        return Response(self.OutputSerializer(product, context={"request": request}).data)

    @extend_schema(
        summary="Delete a Product",
        description=(
            "Deletes one of the logged-in vendor's own products. Returns 404 "
            "if the product does not exist or belongs to another vendor."
        ),
        tags=["Products"],
        parameters=[
            OpenApiParameter(
                name="product_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description="ID of the product to delete.",
            ),
        ],
        responses={
            204: OpenApiResponse(description="Product deleted. No content."),
            403: FORBIDDEN_RESPONSE,
            404: ProductNotFoundSerializer,
        },
    )
    def delete(self, request, product_id):
        product = self._get_owned_product(request, product_id)
        if product is None:
            return Response(
                {"message": "Product not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        product_delete(product=product, user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)