from products.permissions import IsApprovedVendor


class IsVendorAccount(IsApprovedVendor):
    message = "Only vendors can manage delivery settings."
