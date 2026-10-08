from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers, status
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.services import vendor_register, employee_register, user_login


class VendorRegisterApi(APIView):
    permission_classes = [AllowAny]

    class InputSerializer(serializers.Serializer):
        email = serializers.EmailField(max_length=254)
        password = serializers.CharField(write_only=True, min_length=8, max_length=128)
        business_name = serializers.CharField(max_length=255)
        owner_name = serializers.CharField(max_length=255)

    class OutputSerializer(serializers.Serializer):
        id = serializers.IntegerField()
        email = serializers.EmailField()
        role = serializers.CharField(max_length=20)
    @extend_schema(
    request=InputSerializer,
    responses={201: OutputSerializer},
      )
    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = vendor_register(**serializer.validated_data)
        except DjangoValidationError as e:
            return Response({"detail": e.messages}, status=status.HTTP_400_BAD_REQUEST)

        return Response(self.OutputSerializer(user).data, status=status.HTTP_201_CREATED)


class EmployeeRegisterApi(APIView):
    permission_classes = [AllowAny]

    class InputSerializer(serializers.Serializer):
        email = serializers.EmailField(max_length=254)
        password = serializers.CharField(write_only=True, min_length=8, max_length=128)
        full_name = serializers.CharField(max_length=255)

    class OutputSerializer(serializers.Serializer):
        id = serializers.IntegerField()
        email = serializers.EmailField()
        role = serializers.CharField(max_length=20)
    @extend_schema(
    request=InputSerializer,
    responses={201: OutputSerializer},
      )
    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = employee_register(**serializer.validated_data)
        except DjangoValidationError as e:
            return Response({"detail": e.messages}, status=status.HTTP_400_BAD_REQUEST)

        return Response(self.OutputSerializer(user).data, status=status.HTTP_201_CREATED)


class CurrentUserApi(APIView):
    permission_classes = [IsAuthenticated]

    class OutputSerializer(serializers.Serializer):
        role = serializers.CharField()
        verification_status = serializers.SerializerMethodField()

        def get_verification_status(self, user):
            vendor = getattr(user, "vendor_profile", None)
            return vendor.verification_status if vendor else None

    @extend_schema(responses=OutputSerializer)
    def get(self, request):
        return Response(self.OutputSerializer(request.user).data)


class LoginApi(APIView):
    permission_classes = [AllowAny]

    class InputSerializer(serializers.Serializer):
        email = serializers.EmailField(max_length=254)
        password = serializers.CharField(write_only=True, max_length=128)

    class OutputSerializer(serializers.Serializer):
        access = serializers.CharField()
        refresh = serializers.CharField()
        id = serializers.IntegerField()
        email = serializers.EmailField()
        role = serializers.CharField(max_length=20)
    @extend_schema(
    request=InputSerializer,
    responses={200: OutputSerializer},
       )
    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = user_login(**serializer.validated_data)
        except DjangoValidationError as e:
            return Response({"detail": e.messages}, status=status.HTTP_400_BAD_REQUEST)

        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "id": user.id,
            "email": user.email,
            "role": user.role,
        }, status=status.HTTP_200_OK)