from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order
from orders.selectors import order_list_for_user
from orders.services import order_create, order_status_update


def _detail_from(exception):
    if isinstance(exception, DjangoValidationError):
        messages = getattr(exception, "messages", None)
        if messages:
            return "; ".join(str(message) for message in messages)
        return "Invalid request."

    return str(exception) or "Request failed."


class OrderErrorDetailSerializer(serializers.Serializer):
    """Shape of the 400/403 body returned when a service rejects the request."""

    detail = serializers.CharField(
        help_text="Human-readable error message. Multiple messages are joined with '; '.",
    )

    class Meta:
        ref_name = "OrderErrorDetail"


ORDER_VALIDATION_ERROR_DESCRIPTION = (
    "Validation failed. Either a service-level error "
    '(`{"detail": "..."}`) or field-level errors '
    '(`{"field_name": ["..."]}`).'
)


class OrderItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(
        min_value=1,
        help_text="ID of the product being ordered. Must belong to the selected vendor.",
    )
    quantity = serializers.IntegerField(
        min_value=1,
        max_value=100,
        help_text="Number of units, from 1 to 100.",
    )

    class Meta:
        ref_name = "OrderItemInput"


class OrderItemOutputSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    product_id = serializers.IntegerField()
    product_name = serializers.CharField(source="product.name")
    quantity = serializers.IntegerField()
    unit_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price per unit at the time the order was placed.",
    )
    subtotal = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="unit_price multiplied by quantity.",
    )

    class Meta:
        ref_name = "OrderItemOutput"


class OrderListOutputSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    order_code = serializers.CharField()
    employee = serializers.IntegerField(source="employee_id")
    vendor = serializers.IntegerField(source="vendor_id")
    vendor_name = serializers.CharField(source="vendor.business_name")
    delivery_window = serializers.IntegerField(source="delivery_window_id")
    delivery_date = serializers.DateField()
    selected_window_name = serializers.CharField()
    selected_start_time = serializers.TimeField()
    selected_end_time = serializers.TimeField()
    items = OrderItemOutputSerializer(
        many=True,
        source="order_items",
    )
    subtotal = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Sum of all item subtotals, before the delivery fee.",
    )
    delivery_fee = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    total_amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        source="total",
        help_text="subtotal plus delivery_fee.",
    )
    status = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    class Meta:
        ref_name = "OrderListOutput"


class OrderListApi(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List My Orders",
        description=(
            "Returns the orders visible to the logged-in user. "
            "Requires a valid access token."
        ),
        tags=["Orders"],
        responses={
            status.HTTP_200_OK: OrderListOutputSerializer(many=True),
        },
    )
    def get(self, request):
        orders = order_list_for_user(user=request.user)

        return Response(
            OrderListOutputSerializer(orders, many=True).data,
            status=status.HTTP_200_OK,
        )


class OrderCreateApi(APIView):
    permission_classes = [IsAuthenticated]

    class InputSerializer(serializers.Serializer):
        vendor_id = serializers.IntegerField(
            min_value=1,
            help_text="ID of the vendor the order is placed with.",
        )
        items = OrderItemInputSerializer(
            many=True,
            help_text="At least one item. The same product cannot appear twice.",
        )
        selected_delivery_window = serializers.IntegerField(
            min_value=1,
            help_text="ID of one of the vendor's delivery windows.",
        )
        delivery_date = serializers.DateField(
            help_text="Requested delivery date (YYYY-MM-DD).",
        )

        class Meta:
            ref_name = "OrderCreateInput"

        def validate_items(self, value):
            if not value:
                raise serializers.ValidationError(
                    "Items cannot be empty."
                )

            product_ids = [item["product_id"] for item in value]

            if len(product_ids) != len(set(product_ids)):
                raise serializers.ValidationError(
                    "Duplicate products are not allowed in one order."
                )

            return value

    class OutputSerializer(serializers.Serializer):
        id = serializers.IntegerField()
        order_code = serializers.CharField()
        employee = serializers.IntegerField(source="employee_id")
        vendor = serializers.IntegerField(source="vendor_id")
        vendor_name = serializers.CharField(
            source="vendor.business_name"
        )
        delivery_window = serializers.IntegerField(
            source="delivery_window_id"
        )
        delivery_date = serializers.DateField()
        selected_window_name = serializers.CharField()
        selected_start_time = serializers.TimeField()
        selected_end_time = serializers.TimeField()
        items = OrderItemOutputSerializer(
            many=True,
            source="order_items",
        )
        subtotal = serializers.DecimalField(
            max_digits=10,
            decimal_places=2,
            help_text="Sum of all item subtotals, before the delivery fee.",
        )
        delivery_fee = serializers.DecimalField(
            max_digits=10,
            decimal_places=2,
        )
        total_amount = serializers.DecimalField(
            max_digits=10,
            decimal_places=2,
            source="total",
            help_text="subtotal plus delivery_fee.",
        )
        status = serializers.CharField()
        created_at = serializers.DateTimeField()
        updated_at = serializers.DateTimeField()

        class Meta:
            ref_name = "OrderCreateOutput"

    @extend_schema(
        summary="Create an Order",
        description=(
            "Places a new order with a vendor for a chosen delivery window and date. "
            "Requires a valid access token. Returns 400 when validation fails "
            "(for example an empty or duplicated item list) and 403 when the "
            "logged-in user is not allowed to place orders."
        ),
        tags=["Orders"],
        request=InputSerializer,
        responses={
            status.HTTP_201_CREATED: OutputSerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiTypes.OBJECT,
            status.HTTP_403_FORBIDDEN: OrderErrorDetailSerializer,
        },
        examples=[
            OpenApiExample(
                "Create order request",
                value={
                    "vendor_id": 1,
                    "items": [
                        {"product_id": 3, "quantity": 2},
                        {"product_id": 5, "quantity": 1},
                    ],
                    "selected_delivery_window": 2,
                    "delivery_date": "2026-10-20",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Duplicate products",
                value={"items": ["Duplicate products are not allowed in one order."]},
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Service-level error",
                value={"detail": "Request failed."},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            order = order_create(
                user=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            return Response(
                {"detail": _detail_from(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DjangoPermissionDenied as exc:
            return Response(
                {"detail": _detail_from(exc)},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(
            self.OutputSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )


class OrderStatusUpdateApi(APIView):
    permission_classes = [IsAuthenticated]

    class InputSerializer(serializers.Serializer):
        status = serializers.ChoiceField(
            choices=Order.Status.choices,
            help_text="The new status for the order.",
        )

        class Meta:
            ref_name = "OrderStatusUpdateInput"

    class OutputSerializer(serializers.Serializer):
        id = serializers.IntegerField()
        status = serializers.CharField()
        updated_at = serializers.DateTimeField()

        class Meta:
            ref_name = "OrderStatusUpdateOutput"

    @extend_schema(
        summary="Update Order Status",
        description=(
            "Moves an order to a new status. Requires a valid access token. "
            "Returns 400 when the transition is not valid and 403 when the "
            "logged-in user is not allowed to change this order's status."
        ),
        tags=["Orders"],
        parameters=[
            OpenApiParameter(
                name="order_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description="ID of the order to update.",
            ),
        ],
        request=InputSerializer,
        responses={
            status.HTTP_200_OK: OutputSerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiTypes.OBJECT,
            status.HTTP_403_FORBIDDEN: OrderErrorDetailSerializer,
        },
    )
    def patch(self, request, order_id):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            order = order_status_update(
                user=request.user,
                order_id=order_id,
                new_status=serializer.validated_data["status"],
            )
        except DjangoValidationError as exc:
            return Response(
                {"detail": _detail_from(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DjangoPermissionDenied as exc:
            return Response(
                {"detail": _detail_from(exc)},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(
            self.OutputSerializer(order).data,
            status=status.HTTP_200_OK,
        )