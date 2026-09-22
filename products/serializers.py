from rest_framework import serializers

from .models import Product


class ProductSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

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

        read_only_fields = [
            "id",
            "vendor",
            "created_at",
            "updated_at",
            "deleted_at",
        ]

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Price must be greater than 0."
            )

        return value