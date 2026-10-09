from django.contrib import admin, messages
from django.db import transaction

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
	readonly_fields = ("created_at", "updated_at", "verification_status", "is_active")
	actions = ("approve_vendors", "decline_vendors")

	@admin.action(description="Approve selected vendors")
	def approve_vendors(self, request, queryset):
		updated = 0
		with transaction.atomic():
			for vendor in queryset.select_related("user"):
				if vendor.verification_status == VendorProfile.VerificationStatus.APPROVED:
					continue
				vendor.verification_status = VendorProfile.VerificationStatus.APPROVED
				vendor.is_active = True
				vendor.decline_reason = ""
				vendor.save(update_fields=["verification_status", "is_active", "decline_reason", "updated_at"])
				updated += 1
		self.message_user(request, f"Approved {updated} vendor(s).", messages.SUCCESS)

	@admin.action(description="Decline selected vendors")
	def decline_vendors(self, request, queryset):
		updated = 0
		with transaction.atomic():
			for vendor in queryset.select_related("user"):
				if vendor.verification_status == VendorProfile.VerificationStatus.DECLINED:
					continue
				vendor.verification_status = VendorProfile.VerificationStatus.DECLINED
				vendor.is_active = False
				vendor.save(update_fields=["verification_status", "is_active", "updated_at"])
				updated += 1
		self.message_user(request, f"Declined {updated} vendor(s).", messages.SUCCESS)
