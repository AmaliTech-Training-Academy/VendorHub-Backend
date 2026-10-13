from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_field
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.services import employee_register, user_login, vendor_register


class ErrorDetailSerializer(serializers.Serializer):
    """Shape of the 400 body returned when a service raises a validation error."""

    detail = serializers.ListField(child=serializers.CharField())

    class Meta:
        ref_name = "ErrorDetail"


VALIDATION_ERROR_DESCRIPTION = (
    "Validation failed. Either a service-level error "
    '(`{"detail": ["..."]}`) or field-level errors '
    '(`{"field_name": ["..."]}`).'
)


class VendorRegisterApi(APIView):
    permission_classes = [AllowAny]

    class InputSerializer(serializers.Serializer):
        email = serializers.EmailField(max_length=254)
        password = serializers.CharField(
            write_only=True,
            min_length=8,
            max_length=128,
            help_text="8-128 characters.",
        )
        business_name = serializers.CharField(max_length=255)
        owner_name = serializers.CharField(max_length=255)

        class Meta:
            ref_name = "VendorRegisterInput"

    class OutputSerializer(serializers.Serializer):
        id = serializers.IntegerField()
        email = serializers.EmailField()
        role = serializers.CharField(max_length=20)
        business_name = serializers.CharField(source="vendor_profile.business_name")
        owner_name = serializers.CharField(source="vendor_profile.owner_name")

        class Meta:
            ref_name = "VendorRegisterOutput"

    @extend_schema(
        summary="Register a Vendor",
        description=(
            "Creates a new vendor account together with its vendor profile. "
            "No authentication is required. The vendor's profile starts "
            "unverified; check `verification_status` via the current-user endpoint."
        ),
        tags=["Registration"],
        request=InputSerializer,
        responses={
            201: OutputSerializer,
            400: ErrorDetailSerializer,
        },
        examples=[
            OpenApiExample(
                "Vendor registration",
                value={
                    "email": "vendor@example.com",
                    "password": "StrongPass123",
                    "business_name": "Ama's Kitchen",
                    "owner_name": "Ama Mensah",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Email already in use",
                value={"detail": ["A user with this email already exists."]},
                response_only=True,
                status_codes=["400"],
            ),
        ],
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
        password = serializers.CharField(
            write_only=True,
            min_length=8,
            max_length=128,
            help_text="8-128 characters.",
        )
        full_name = serializers.CharField(max_length=255)

        class Meta:
            ref_name = "EmployeeRegisterInput"

    class OutputSerializer(serializers.Serializer):
        id = serializers.IntegerField()
        email = serializers.EmailField()
        role = serializers.CharField(max_length=20)

        class Meta:
            ref_name = "EmployeeRegisterOutput"

    @extend_schema(
        summary="Register an Employee",
        description=(
            "Creates a new employee account together with its employee profile. "
            "No authentication is required."
        ),
        tags=["Registration"],
        request=InputSerializer,
        responses={
            201: OutputSerializer,
            400: ErrorDetailSerializer,
        },
        examples=[
            OpenApiExample(
                "Employee registration",
                value={
                    "email": "employee@example.com",
                    "password": "StrongPass123",
                    "full_name": "Kofi Boateng",
                },
                request_only=True,
            ),
        ],
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

        class Meta:
            ref_name = "CurrentUser"

        @extend_schema_field(serializers.CharField(allow_null=True))
        def get_verification_status(self, user):
            vendor = getattr(user, "vendor_profile", None)
            return vendor.verification_status if vendor else None

    @extend_schema(
        summary="Get Current User",
        description=(
            "Returns the role of the logged-in user. `verification_status` is the "
            "vendor's verification state for vendor accounts and `null` for "
            "everyone else. Requires a valid access token."
        ),
        tags=["Current User"],
        responses={200: OutputSerializer},
    )
    def get(self, request):
        return Response(self.OutputSerializer(request.user).data)


class LoginApi(APIView):
    permission_classes = [AllowAny]

    class InputSerializer(serializers.Serializer):
        email = serializers.EmailField(max_length=254)
        password = serializers.CharField(write_only=True, max_length=128)

        class Meta:
            ref_name = "LoginInput"

    class OutputSerializer(serializers.Serializer):
        access = serializers.CharField(help_text="Short-lived JWT access token.")
        refresh = serializers.CharField(help_text="JWT refresh token.")
        id = serializers.IntegerField()
        email = serializers.EmailField()
        role = serializers.CharField(max_length=20)
        name = serializers.CharField(
            help_text="Business name for vendors, full name for employees.",
        )

        class Meta:
            ref_name = "LoginOutput"

    @extend_schema(
        summary="Log In",
        description=(
            "Authenticates a user with email and password and returns a JWT "
            "access/refresh pair plus basic user details. Send the access token "
            "as `Authorization: Bearer <token>` on protected endpoints."
        ),
        tags=["Authentication"],
        request=InputSerializer,
        responses={
            200: OutputSerializer,
            400: ErrorDetailSerializer,
        },
        examples=[
            OpenApiExample(
                "Login request",
                value={"email": "vendor@example.com", "password": "StrongPass123"},
                request_only=True,
            ),
            OpenApiExample(
                "Invalid credentials",
                value={"detail": ["Invalid email or password."]},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = user_login(**serializer.validated_data)
        except DjangoValidationError as e:
            return Response({"detail": e.messages}, status=status.HTTP_400_BAD_REQUEST)

        if user.role == "VENDOR":
            name = user.vendor_profile.business_name
        else:
            name = user.employee_profile.full_name

        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "name": name
        }, status=status.HTTP_200_OK)