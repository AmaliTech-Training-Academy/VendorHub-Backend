from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.services import order_create

def _detail_from(exception):
    if isinstance(exception, DjangoValidationError):
        messages = getattr(exception, "messages", None)

        if messages:
            return "; ".join(str(message) for message in messages)

        return "Invalid request."

    return str(exception) or "Request failed."

class OrderItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(
        min_value=1,
        max_value=100,
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
    )

    subtotal = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    class Meta:
        ref_name = "OrderItemOutput"

class OrderCreateApi(APIView):
    permission_classes = [IsAuthenticated]

    class InputSerializer(serializers.Serializer):
        vendor_id = serializers.IntegerField(min_value=1)
        items = OrderItemInputSerializer(many=True)
        selected_delivery_window = serializers.IntegerField(min_value=1)
        delivery_date = serializers.DateField()

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
        )

        delivery_fee = serializers.DecimalField(
            max_digits=10,
            decimal_places=2,
        )

        total_amount_ghs = serializers.DecimalField(
            max_digits=10,
            decimal_places=2,
            source="total",
        )

        status = serializers.CharField()
        created_at = serializers.DateTimeField()
        updated_at = serializers.DateTimeField()

        class Meta:
            ref_name = "OrderCreateOutput"

    @extend_schema(
        request=InputSerializer,
        responses={
            status.HTTP_201_CREATED: OutputSerializer,
        },
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