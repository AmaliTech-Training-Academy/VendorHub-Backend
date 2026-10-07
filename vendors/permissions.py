from products.permissions import IsVendor


class IsVendorAccount(IsVendor):
    message = "Only vendors can manage delivery settings."


class IsStorefrontVendor(IsVendor):
    message = "Only vendors can manage their storefront."
