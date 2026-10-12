from products.permissions import IsApprovedVendor


class IsVendorAccount(IsApprovedVendor):
    message = "Only vendors can manage delivery settings."


class IsStorefrontVendor(IsVendorAccount):
    message = "Only vendors can manage their storefront."
