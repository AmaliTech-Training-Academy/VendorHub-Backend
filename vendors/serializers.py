from rest_framework import serializers
from accounts.models import VendorProfile
from products.models import Product

class VendorStorefrontSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorProfile
        fields = [
            "id",
            "business_name",
            "owner_name",
            "delivery_fee",
            "is_active",
        ]

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "category",
            "price",
            "in_stock",
        ]