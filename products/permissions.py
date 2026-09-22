from rest_framework.permissions import BasePermission


class IsVendor(BasePermission):
    message = "Only vendors can manage vendor products."

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role == "VENDOR"
            and hasattr(request.user, "vendor_profile")
        )