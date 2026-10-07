from django.contrib import admin

from accounts.models import VendorProfile


@admin.register(VendorProfile)
class VendorProfileAdmin(admin.ModelAdmin):
	list_display = (
		"business_name",
		"owner_name",
		"verification_status",
		"decline_reason",
		"is_active",
		"created_at",
	)
	list_filter = ("verification_status", "is_active")
	list_editable = ("decline_reason",)
	search_fields = ("business_name", "owner_name", "user__email")
	readonly_fields = ("created_at", "updated_at")
	actions = ("approve_vendors", "decline_vendors")

	@admin.action(description="Approve selected vendors")
	def approve_vendors(self, request, queryset):
		for vendor in queryset.select_related("user"):
			if vendor.verification_status == VendorProfile.VerificationStatus.APPROVED:
				continue
			vendor.verification_status = VendorProfile.VerificationStatus.APPROVED
			vendor.is_active = True
			vendor.decline_reason = ""
			vendor.save(update_fields=["verification_status", "is_active", "decline_reason", "updated_at"])

	@admin.action(description="Decline selected vendors")
	def decline_vendors(self, request, queryset):
		for vendor in queryset.select_related("user"):
			if vendor.verification_status == VendorProfile.VerificationStatus.DECLINED:
				continue
			vendor.verification_status = VendorProfile.VerificationStatus.DECLINED
			vendor.is_active = False
			vendor.save(update_fields=["verification_status", "is_active", "updated_at"])
