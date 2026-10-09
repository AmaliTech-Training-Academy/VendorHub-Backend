from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from accounts.models import VendorProfile


@receiver(pre_save, sender=VendorProfile)
def track_verification_status_change(sender, instance, **kwargs):
    if kwargs.get("raw") or not instance.pk:
        instance._verification_status_changed_to = None
        return

    update_fields = kwargs.get("update_fields")
    if update_fields is not None and "verification_status" not in update_fields:
        instance._verification_status_changed_to = None
        return

    previous_status = (
        sender.objects.filter(pk=instance.pk)
        .values_list("verification_status", flat=True)
        .first()
    )
    instance._verification_status_changed_to = (
        instance.verification_status
        if previous_status is not None and previous_status != instance.verification_status
        else None
    )


@receiver(post_save, sender=VendorProfile)
def send_verification_status_email(sender, instance, **kwargs):
    if kwargs.get("raw"):
        return

    status = getattr(instance, "_verification_status_changed_to", None)
    if status not in {
        VendorProfile.VerificationStatus.APPROVED,
        VendorProfile.VerificationStatus.DECLINED,
    }:
        return

    from notifications.services import send_vendor_approved, send_vendor_declined

    send_email = (
        send_vendor_approved
        if status == VendorProfile.VerificationStatus.APPROVED
        else send_vendor_declined
    )
    transaction.on_commit(lambda: send_email(instance), robust=True)