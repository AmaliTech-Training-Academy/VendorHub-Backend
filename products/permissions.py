from rest_framework.permissions import BasePermission


class IsVendor(BasePermission):
    message = "Only vendors can manage vendor products."

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role == "VENDOR"
            and hasattr(request.user, "vendor_profile")
        )


class IsApprovedVendor(IsVendor):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and (
            request.user.vendor_profile.verification_status
            == request.user.vendor_profile.VerificationStatus.APPROVED
            and request.user.vendor_profile.is_active
        )