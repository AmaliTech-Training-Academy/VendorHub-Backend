from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema, extend_schema_field
from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import VendorProfile
from products.models import Product

from .models import DeliveryWindow, Weekday
from .pagination import VendorPagination
from .permissions import IsVendorAccount
from .selectors import (
    vendor_available_days,
    vendor_categories,
    vendor_get,
    vendor_get_for_user,
    vendor_product_list,
    vendor_storefront_list,
)
from .services import delivery_settings_update

AVAILABLE_DAYS_SCHEMA = serializers.ListField(child=serializers.ChoiceField(choices=Weekday.choices))
CATEGORIES_SCHEMA = serializers.ListField(child=serializers.CharField())


class DeliveryWindowOutputSerializer(serializers.ModelSerializer):
    start_time = serializers.TimeField(format="%H:%M")
    end_time = serializers.TimeField(format="%H:%M")

    class Meta:
        model = DeliveryWindow
        ref_name = "DeliveryWindow"
        fields = [
            "id",
            "window_name",
            "start_time",
            "end_time",
            "sort_order",
        ]
        read_only_fields = fields


class VendorListApi(GenericAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class = VendorPagination

    class OutputSerializer(serializers.ModelSerializer):
        categories = serializers.SerializerMethodField()
        available_days = serializers.SerializerMethodField()
        delivery_windows = DeliveryWindowOutputSerializer(
            many=True,
            source="active_delivery_windows",
            read_only=True,
        )

        class Meta:
            model = VendorProfile
            ref_name = "VendorStorefront"
            fields = [
                "id",
                "business_name",
                "categories",
                "delivery_fee",
                "available_days",
                "delivery_windows",
            ]
            read_only_fields = fields

        @extend_schema_field(CATEGORIES_SCHEMA)
        def get_categories(self, vendor):
            return vendor_categories(vendor=vendor)

        @extend_schema_field(AVAILABLE_DAYS_SCHEMA)
        def get_available_days(self, vendor):
            return vendor_available_days(vendor=vendor)

    @extend_schema(
        summary="List Active Vendors",
        tags=["Vendor Storefront"],
        responses=OutputSerializer(many=True),
    )
    def get(self, request):
        page = self.paginate_queryset(vendor_storefront_list())
        serializer = self.OutputSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)


class VendorProductListApi(GenericAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class = VendorPagination

    class FilterSerializer(serializers.Serializer):
        vendor_id = serializers.IntegerField(min_value=1)

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
        parameters=[FilterSerializer],
        responses=OutputSerializer(many=True),
    )
    def get(self, request):
        filters = self.FilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)

        vendor = vendor_get(vendor_id=filters.validated_data["vendor_id"])
        if vendor is None:
            return Response(
                {"detail": "Vendor not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        page = self.paginate_queryset(vendor_product_list(vendor_id=vendor.id))
        serializer = self.OutputSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)


class MyDeliverySettingsApi(APIView):
    # The logged-in vendor's own settings. The vendor comes from the login token, never from the URL,
    # so there is no id an attacker could change to reach another vendor.
    permission_classes = [IsAuthenticated, IsVendorAccount]

    class InputSerializer(serializers.Serializer):
        class WindowSerializer(serializers.Serializer):
            id = serializers.IntegerField(required=False)
            window_name = serializers.CharField(max_length=100)
            start_time = serializers.TimeField()
            end_time = serializers.TimeField()

            class Meta:
                ref_name = "DeliveryWindowInput"

            def validate(self, data):
                if data["end_time"] <= data["start_time"]:
                    raise serializers.ValidationError("end_time must be after start_time.")

                return data

        available_days = serializers.ListField(
            child=serializers.ChoiceField(choices=Weekday.choices),
            min_length=1,
        )
        delivery_fee = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
        time_windows = WindowSerializer(many=True, allow_empty=False)

        class Meta:
            ref_name = "DeliverySettingsInput"

        def validate_time_windows(self, windows):
            names = [window["window_name"].strip().lower() for window in windows]
            if len(names) != len(set(names)):
                raise serializers.ValidationError("Window names must be unique.")

            ids = [window["id"] for window in windows if "id" in window]
            if len(ids) != len(set(ids)):
                raise serializers.ValidationError("Each window can only be listed once.")

            # Every window runs on the same days, so no two windows may overlap in time.
            by_start = sorted(windows, key=lambda window: window["start_time"])
            for earlier, later in zip(by_start, by_start[1:]):
                if later["start_time"] < earlier["end_time"]:
                    raise serializers.ValidationError(
                        f'"{earlier["window_name"]}" and "{later["window_name"]}" overlap.'
                    )

            return windows

    class OutputSerializer(serializers.Serializer):
        available_days = serializers.SerializerMethodField()
        delivery_fee = serializers.DecimalField(max_digits=10, decimal_places=2)
        time_windows = DeliveryWindowOutputSerializer(many=True, source="active_delivery_windows")

        class Meta:
            ref_name = "DeliverySettings"

        @extend_schema_field(AVAILABLE_DAYS_SCHEMA)
        def get_available_days(self, vendor):
            return vendor_available_days(vendor=vendor)

    @extend_schema(
        summary="Get My Delivery Settings",
        tags=["Vendor Delivery Settings"],
        responses=OutputSerializer,
    )
    def get(self, request):
        vendor = vendor_get_for_user(user=request.user)
        if vendor is None:
            return self.inactive_vendor_response()

        return Response(self.OutputSerializer(vendor).data)

    @extend_schema(
        summary="Update My Delivery Settings",
        tags=["Vendor Delivery Settings"],
        request=InputSerializer,
        responses=OutputSerializer,
    )
    def put(self, request):
        if vendor_get_for_user(user=request.user) is None:
            return self.inactive_vendor_response()

        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            delivery_settings_update(user=request.user, **serializer.validated_data)
        except DjangoValidationError as e:
            return Response({"detail": e.messages[0]}, status=status.HTTP_400_BAD_REQUEST)

        return Response(self.OutputSerializer(vendor_get_for_user(user=request.user)).data)

    @staticmethod
    def inactive_vendor_response():
        return Response(
            {"detail": "Inactive vendors cannot manage delivery settings."},
            status=status.HTTP_403_FORBIDDEN,
        )
