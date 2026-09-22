from rest_framework import serializers
from accounts.models import VendorProfile

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